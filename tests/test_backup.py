from pathlib import Path

from classroom.app.classroom_service.backup import backup, restore


def test_backup_restore_round_trip(service, tmp_path):
    root = tmp_path
    root.mkdir(exist_ok=True)
    db_path = root / "backup.db"
    archive = root / "backup.zip"
    restored = root / "restored"
    for path in (db_path, archive):
        path.unlink(missing_ok=True)
    # Copy the in-memory test data into a file database through SQLite backup.
    import sqlite3
    disk = sqlite3.connect(db_path)
    source = service.db.connect()
    source.backup(disk)
    source.close(); disk.close()
    blobs = root / "data" / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    (blobs / "test.txt").write_text("archive", encoding="utf-8")
    backup(db_path, root / "data", archive)
    result = restore(archive, restored)
    assert result["files"] >= 1
    assert (restored / "classroom.db").exists()
