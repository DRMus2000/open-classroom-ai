"""Initialize/verify the classroom database without touching Open WebUI DB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

from .database import ClassroomDB, SCHEMA_VERSION, MIGRATIONS
from hashlib import sha256


def migrate(path: str, *, verify_only: bool = False) -> dict:
    if not verify_only:
        initialized = ClassroomDB(path)
        initialized.close()
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute("SELECT version,checksum,applied_at FROM schema_migrations ORDER BY version DESC LIMIT 1").fetchone()
        quick = connection.execute("PRAGMA quick_check").fetchone()
        revisions = connection.execute("SELECT version,checksum FROM schema_migrations ORDER BY version").fetchall()
        expected = [(v, sha256(script.encode("utf-8")).hexdigest()) for v, script in MIGRATIONS.items()]
        if [tuple(r) for r in revisions] != expected:
            raise RuntimeError("classroom schema checksum mismatch")
        reference = sqlite3.connect(':memory:')
        try:
            for script in MIGRATIONS.values():
                reference.executescript(script)
            query = "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
            if [tuple(r) for r in connection.execute(query)] != reference.execute(query).fetchall():
                raise RuntimeError('classroom schema objects differ from the verified migrations')
        finally:
            reference.close()
    finally:
        connection.close()
    result = {"database": str(Path(path)), "schema_version": row["version"] if row else None, "checksum": row["checksum"] if row else None, "applied_at": row["applied_at"] if row else None, "quick_check": quick[0] if quick else "unknown", "verify_only": verify_only}
    if result["quick_check"] != "ok" or result["schema_version"] != SCHEMA_VERSION:
        raise RuntimeError("classroom database failed migration verification")
    return result


def main() -> None:  # pragma: no cover - command wrapper
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate(args.db, verify_only=args.verify_only), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
