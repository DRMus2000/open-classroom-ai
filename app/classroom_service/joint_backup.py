"""Offline joint backup of native accounts/chats and classroom records."""
from contextlib import ExitStack, closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import uuid
import zipfile

from .backup import _sha
from .runtime import InstanceLock


def joint_backup(db_path, data_root, native_root, output):
    db_path, data_root, native_root, output = map(lambda p: Path(p).resolve(), (db_path, data_root, native_root, output))
    native_db = native_root / 'webui.db'
    if not db_path.is_file() or not native_db.is_file():
        raise ValueError('both classroom.db and native webui.db are required')
    if data_root == native_root:
        raise ValueError('classroom and native data directories must be separate')
    output.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        for root, filename in ((data_root, 'service.lock'), (native_root, 'webui.lock')):
            lock = InstanceLock(root / filename).acquire()
            stack.callback(lock.close)
        staging = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='.joint-backup-', dir=output.parent)))
        files = {}
        databases = ((db_path, 'classroom.db'), (native_db, 'openwebui/webui.db'))
        for source, name in databases:
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            a = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
            b = sqlite3.connect(target)
            try:
                a.backup(b)
                if b.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('database integrity check failed')
            finally:
                a.close(); b.close()
            files[name] = target
        # Only durable installation data, not logs, cache, exports or live WAL.
        for root, prefix, selected in ((data_root, '', ['blobs', 'legacy', 'bridge.key']),
                                      (native_root, 'openwebui/', ['uploads', '.webui_secret_key', 'classroom-baseline.json'])):
            for item in selected:
                start = root / item
                paths = start.rglob('*') if start.is_dir() else [start]
                for path in paths:
                    if path.is_symlink():
                        raise ValueError('data backup does not follow symlinks')
                    if path.is_file():
                        files[prefix + path.relative_to(root).as_posix()] = path
        temporary = staging / 'verified.zip'
        upload_paths = {}
        with closing(sqlite3.connect(staging / 'openwebui/webui.db')) as native:
            if native.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='file'").fetchone():
                for file_id, stored_path in native.execute('SELECT id,path FROM file WHERE path IS NOT NULL'):
                    path = Path(stored_path)
                    if not path.is_absolute():
                        path = native_root / path
                    path = path.resolve()
                    uploads = (native_root / 'uploads').resolve()
                    if uploads not in path.parents:
                        raise ValueError('native attachment path is outside uploads')
                    member = 'openwebui/uploads/' + path.relative_to(uploads).as_posix()
                    if member not in files:
                        raise ValueError('native attachment is missing from backup')
                    upload_paths[file_id] = member
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            hashes = {}
            for name, path in files.items():
                archive.write(path, name)
                hashes[name] = _sha(path)
            archive.writestr('manifest.json', json.dumps({'format_version': 1, 'scope': 'joint-offline',
                'backup_id': uuid.uuid4().hex, 'files': hashes, 'native_upload_paths': upload_paths, 'contains_secrets': True}, indent=2))
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip():
                raise ValueError('backup archive integrity failed')
        os.replace(temporary, output)
    return output
