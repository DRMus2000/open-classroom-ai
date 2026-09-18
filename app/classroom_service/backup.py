"""Consistent classroom DB/blob backup and restore helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def backup(db_path: str | Path, data_root: str | Path, output: str | Path) -> Path:
    db_path, data_root, output = Path(db_path), Path(data_root), Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep the SQLite snapshot beside the requested output.  This avoids a
    # system-temp directory that can be inaccessible to a portable Windows
    # runtime under a restricted teacher account.
    temp_db = output.with_name(output.name + ".snapshot.db")
    temp_db.unlink(missing_ok=True)
    source = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    target = sqlite3.connect(temp_db)
    try:
        source.backup(target)
    finally:
        target.close(); source.close()
    files = {"classroom.db": _sha(temp_db)}
    try:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_db, "classroom.db")
            blobs = data_root / "blobs"
            if blobs.exists():
                for path in blobs.rglob("*"):
                    if path.is_file():
                        rel = path.relative_to(data_root).as_posix()
                        archive.write(path, rel)
                        files[rel] = _sha(path)
            manifest = {"format_version": 1, "backup_id": uuid.uuid4().hex, "files": files, "contains_secrets": False}
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    finally:
        temp_db.unlink(missing_ok=True)
    return output


def restore(backup_path: str | Path, target_root: str | Path) -> dict:
    backup_path, target_root = Path(backup_path), Path(target_root).absolute()
    if target_root.is_symlink() or (target_root.exists() and
            (not target_root.is_dir() or any(target_root.iterdir()))):
        raise ValueError("restore requires a new or empty directory; existing data is never overwritten")
    target_root.parent.mkdir(parents=True, exist_ok=True)
    # Validate in a private sibling directory on the same volume.  No target
    # file is touched until every hash and database has passed validation.
    with tempfile.TemporaryDirectory(prefix=".classroom-restore-", dir=target_root.parent) as temporary:
        staging = Path(temporary) / "verified"
        staging.mkdir()
        with zipfile.ZipFile(backup_path) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(set(name.casefold() for name in names)):
                raise ValueError("duplicate archive paths")
            if "manifest.json" not in names or archive.getinfo("manifest.json").file_size > 16 * 1024 * 1024:
                raise ValueError("missing or oversized backup manifest")
            manifest = json.loads(archive.read("manifest.json"))
            files = manifest.get("files")
            if manifest.get("format_version") != 1 or not isinstance(files, dict) or "classroom.db" not in files:
                raise ValueError("unsupported or incomplete backup format")
            if set(names) != set(files) | {"manifest.json"}:
                raise ValueError("backup file list does not match manifest")
            for name, expected_hash in files.items():
                if (not isinstance(name, str) or "\\" in name or ":" in name
                        or any(part in {"", ".", ".."} or part.endswith((" ", ".")) for part in name.split("/"))):
                    raise ValueError("invalid backup path")
                path = (staging / name).resolve()
                if staging.resolve() not in path.parents:
                    raise ValueError("backup path escaped staging directory")
                if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                    raise ValueError("invalid backup hash")
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, path.open("xb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                if _sha(path) != expected_hash:
                    raise ValueError(f"backup hash mismatch: {name}")
                if name.endswith(".db"):
                    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                    try:
                        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                            raise ValueError(f"invalid SQLite database: {name}")
                    finally:
                        connection.close()
        # Hash verification is complete. Rebase native file references only in
        # the validated staging DB so a restored installation is independent.
        upload_paths = manifest.get('native_upload_paths', {})
        if upload_paths:
            with closing(sqlite3.connect(staging / 'openwebui/webui.db')) as native:
                for file_id, member in upload_paths.items():
                    if member not in manifest['files'] or not member.startswith('openwebui/uploads/'):
                        raise ValueError('invalid native upload relocation manifest')
                    native.execute('UPDATE file SET path=? WHERE id=?', (str(target_root / member), file_id))
                native.commit()
        if target_root.exists():
            target_root.rmdir()  # Only an empty directory can be removed.
        staging.rename(target_root)
    return {"backup_id": manifest.get("backup_id"), "files": len(manifest.get("files", {})), "target": str(target_root)}


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("backup"); create.add_argument("--db", required=True); create.add_argument("--data-root", required=True); create.add_argument("--output", required=True)
    create.add_argument("--native-root", required=True)
    recover = sub.add_parser("restore"); recover.add_argument("--backup", required=True); recover.add_argument("--target-root", required=True)
    args = parser.parse_args()
    from .joint_backup import joint_backup
    result = joint_backup(args.db, args.data_root, args.native_root, args.output) if args.command == "backup" else restore(args.backup, args.target_root)
    print(json.dumps(str(result) if isinstance(result, Path) else result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
