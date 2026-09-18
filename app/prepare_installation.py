"""Rehearse migration into a NEW installation; source databases stay read-only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import subprocess
import time
from contextlib import closing
import struct
import traceback
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parent))


def redact_diagnostics(text):
    for key, value in os.environ.items():
        if len(value) >= 4 and any(word in key.upper() for word in ('PASSWORD', 'SECRET', 'TOKEN', 'API_KEY')):
            text = text.replace(value, '[REDACTED]')
    return text


def native_schema_failure(result):
    def decode(value):
        return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
    return RuntimeError(redact_diagnostics(
        'Native schema reference process failed (exit code ' + str(result.returncode) + ').\n'
        + '--- native stderr ---\n' + decode(result.stderr)
        + '\n--- native stdout ---\n' + decode(result.stdout)))


def schema(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        return db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND name<>'alembic_version' ORDER BY type,name").fetchall()


def schema_hash(path):
    return hashlib.sha256(json.dumps(schema(path), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def snapshot(source, target):
    source = Path(source).resolve()
    a = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    b = sqlite3.connect(target)
    try:
        a.backup(b)
        if b.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('source snapshot failed integrity check')
    finally:
        a.close(); b.close()


def prepare(native_root, destination, legacy_review=None):
    native_root = Path(native_root).resolve() if native_root else None
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('destination must not exist')
    if native_root and not (native_root / 'webui.db').is_file():
        raise ValueError('native webui.db is required')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.classroom-migration-', dir=destination.parent) as temporary:
        work = Path(temporary)
        installation = work / 'installation'
        native = installation / 'openwebui'
        classroom = installation / 'classroom'
        native.mkdir(parents=True); classroom.mkdir()
        if native_root:
            snapshot(native_root / 'webui.db', native / 'webui.db')
        for item in (('uploads', '.webui_secret_key') if native_root else ()):
            source = native_root / item
            if source.is_dir():
                shutil.copytree(source, native / item)
            elif source.is_file():
                shutil.copy2(source, native / item)
        legacy_secret = native_root.parent.parent / '.webui_secret_key' if native_root else None
        if legacy_secret and not (native / '.webui_secret_key').exists() and legacy_secret.is_file():
            shutil.copy2(legacy_secret, native / '.webui_secret_key')
        # Import exact bundled models against isolated storage only. No native
        # migration history is guessed or stamped.
        env = os.environ.copy()
        env.update(DATA_DIR=str(work / 'metadata-data'), DATABASE_URL='sqlite:///' + str(work / 'metadata-import.db'),
                          WEBUI_SECRET_KEY='isolated-schema-verification-only', ENABLE_DB_MIGRATIONS='false', FROM_INIT_PY='true',
                          OFFLINE_MODE='true', HF_HUB_OFFLINE='1', PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
        reference = work / 'reference.db'
        code = "import sys; import open_webui.main; from open_webui.internal.db import Base; from sqlalchemy import create_engine; engine=create_engine('sqlite:///'+sys.argv[1]); Base.metadata.create_all(engine); engine.dispose()"
        result = subprocess.run([sys.executable, '-B', '-c', code, str(reference)], env=env, capture_output=True, timeout=300)
        if result.returncode:
            raise native_schema_failure(result)
        if native_root is None:
            snapshot(reference, native / 'webui.db')
        actual, expected = schema(native / 'webui.db'), schema(reference)
        if actual != expected:
            # Fail with object names only; never dump auth/config values.
            a, b = {(r[0], r[1]): r for r in actual}, {(r[0], r[1]): r for r in expected}
            changes = [str(k) for k in a.keys() | b.keys() if a.get(k) != b.get(k)]
            raise RuntimeError('native schema requires an explicit migration: ' + ', '.join(sorted(changes)))
        # Apply only to the verified COPY. Empty local embedding model prevents
        # startup downloads; classroom files bypass native retrieval entirely.
        with closing(sqlite3.connect(native / 'webui.db')) as settings:
            from openwebui_bridge.policy import POLICY
            for key, value in POLICY.items():
                settings.execute('INSERT INTO config(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at', (key, json.dumps(value), int(time.time())))
            settings.commit()
        from classroom_service.database import ClassroomDB, json_dumps
        from classroom_service.service import ClassroomService
        from classroom_service.clock import iso
        db = ClassroomDB(classroom / 'classroom.db')
        service = ClassroomService(db, data_root=classroom)
        counts = {}
        content_hashes = {}
        legacy = classroom / 'legacy'
        legacy.mkdir()
        relocated_files = []
        with closing(sqlite3.connect((native / 'webui.db').as_uri() + '?mode=ro', uri=True)) as source:
            source.row_factory = sqlite3.Row
            for row in source.execute('SELECT id,name,email,role FROM user'):
                if row['role'] == 'user':
                    service.enroll_student(row['id'], row['name'], row['email'], must_change_password=True)
                elif row['role'] == 'admin':
                    service.register_teacher(row['id'], row['name'], row['email'])
            for table in ('chat', 'chat_message', 'file'):
                rows = source.execute('SELECT * FROM "' + table + '"').fetchall()
                counts[table] = len(rows)
                with db.transaction() as conn:
                    for index, row in enumerate(rows):
                        value = dict(row)
                        owner = value.get('user_id')
                        if owner is None and value.get('chat_id'):
                            chat_owner = source.execute('SELECT user_id FROM chat WHERE id=?', (value['chat_id'],)).fetchone()
                            owner = chat_owner[0] if chat_owner else None
                        raw = json_dumps(value)
                        if table == 'file' and value.get('path'):
                            original = Path(value['path'])
                            if not original.is_absolute():
                                original = native_root / original
                            original = original.resolve()
                            uploads = (native_root / 'uploads').resolve()
                            if uploads not in original.parents or not original.is_file():
                                raise RuntimeError('legacy attachment is missing or outside native uploads: ' + str(value.get('id')))
                            relative = original.relative_to(uploads)
                            copied = native / 'uploads' / relative
                            digest = hashlib.sha256(copied.read_bytes()).hexdigest()
                            preserved = legacy / 'uploads' / (hashlib.sha256(str(value.get('id')).encode()).hexdigest() + '.bin')
                            preserved.parent.mkdir(exist_ok=True)
                            shutil.copy2(copied, preserved)
                            value['classroom_blob_ref'] = preserved.relative_to(classroom).as_posix()
                            value['classroom_blob_sha256'] = digest
                            relocated_files.append((str(destination / 'openwebui/uploads' / relative), value['id']))
                            raw = json_dumps(value)
                        conn.execute('INSERT INTO legacy_records VALUES(?,?,?,?,?,?,?)', ('openwebui', table, str(value.get('id', index)), owner, raw, hashlib.sha256(raw.encode()).hexdigest(), iso(service.now())))
            counts['user'] = source.execute('SELECT COUNT(*) FROM user').fetchone()[0]
            counts['auth'] = source.execute('SELECT COUNT(*) FROM auth').fetchone()[0]
            for table in ('user', 'auth', 'chat', 'chat_message', 'file'):
                values = [json_dumps(dict(row)) for row in source.execute('SELECT * FROM "' + table + '"')]
                content_hashes[table] = hashlib.sha256('\n'.join(sorted(values)).encode()).hexdigest()
        if relocated_files:
            with closing(sqlite3.connect(native / 'webui.db')) as target:
                target.executemany('UPDATE file SET path=? WHERE id=?', relocated_files)
                target.commit()
        if legacy_review:
            with closing(sqlite3.connect(Path(legacy_review).resolve().as_uri() + '?mode=ro', uri=True)) as source:
                source.row_factory = sqlite3.Row
                rows = source.execute('SELECT * FROM review_requests').fetchall()
                counts['legacy_review'] = len(rows)
                with db.transaction() as conn:
                    for row in rows:
                        raw = json_dumps(dict(row))
                        conn.execute('INSERT INTO legacy_records VALUES(?,?,?,?,?,?,?)', ('review-v1', 'review_request', row['id'], row['user_id'], raw, hashlib.sha256(raw.encode()).hexdigest(), iso(service.now())))
        # Protected source snapshot makes rollback possible without discarding
        # the new installation or post-cutover classroom records.
        snapshot(native_root / 'webui.db' if native_root else native / 'webui.db', legacy / 'original-webui.db')
        if legacy_review:
            snapshot(legacy_review, legacy / 'original-review.db')
        report = {'format_version': 1, 'open_webui': '0.11.2', 'schema_sha256': schema_hash(native / 'webui.db'),
                  'migration_history_written': False, 'source_modified': False, 'counts': counts, 'source_content_sha256': content_hashes, 'legacy_charge_units': 0}
        (native / 'classroom-baseline.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (installation / 'migration-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        db.close()
        # Antivirus/indexing can briefly retain a handle after SQLite closes.
        # Retry the same atomic rename; never copy over an existing target.
        for attempt in range(30):
            try:
                installation.rename(destination)
                break
            except PermissionError:
                if attempt == 29 or destination.exists():
                    raise
                time.sleep(0.1)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--native-root')
    source.add_argument('--new', action='store_true')
    parser.add_argument('--destination', required=True)
    parser.add_argument('--legacy-review')
    parser.add_argument('--friendly', action='store_true', help='show clear initialization status and save failure diagnostics')
    args = parser.parse_args(argv)
    destination = Path(args.destination).resolve()
    if args.friendly:
        print('正在初始化课堂，请等待完成……', flush=True)
    try:
        report = prepare(args.native_root, destination, args.legacy_review)
    except Exception:
        details = redact_diagnostics(traceback.format_exc())
        if args.friendly:
            print('\n初始化未完成。没有覆盖已有课堂数据。', flush=True)
            if destination.exists():
                print('目标数据目录已存在，请勿删除。若此前已初始化成功，请直接运行“启动课堂.cmd”。', flush=True)
            if 'torch_python.dll' in details and 'WinError 126' in details:
                print('PyTorch 的 Windows DLL 依赖加载失败。请先安装或修复微软 Visual C++ x64 运行库，再重试。', flush=True)
                print('微软官方下载：https://aka.ms/vc14/vc_redist.x64.exe', flush=True)
        try:
            folder = destination.parent / 'initialization-logs'
            folder.mkdir(parents=True, exist_ok=True)
            log = folder / ('init-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.log')
            log.write_text('Python: ' + sys.version + '\nExecutable: ' + sys.executable
                           + '\nWindows/platform: ' + (str(sys.getwindowsversion()) if hasattr(sys, 'getwindowsversion') else sys.platform)
                           + '\nPython process bits: ' + str(struct.calcsize('P') * 8)
                           + '\nDestination: ' + str(destination) + '\n\n' + details, encoding='utf-8')
            print('详细诊断日志：' + str(log), flush=True)
            print('请将这份 .log 文件发回，以便确定失败原因。', flush=True)
        except OSError:
            print('无法保存日志，完整错误如下：\n' + details, file=sys.stderr)
        if not args.friendly:
            print(details, file=sys.stderr)
        return 1
    if args.friendly:
        print('\n初始化成功。\n下一步：关闭此窗口，双击“启动课堂.cmd”。\n无需重复初始化。', flush=True)
        print('数据目录：' + str(destination), flush=True)
    else:
        print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
