"""Read the sole native administrator email without loading credentials."""
import argparse
from pathlib import Path
import sqlite3


def administrator_email(native_root):
    db = Path(native_root) / 'webui.db'
    if not db.is_file():
        return None
    try:
        with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            rows = conn.execute('SELECT email FROM "user" WHERE role=? LIMIT 2', ('admin',)).fetchall()
        if len(rows) == 1 and isinstance(rows[0][0], str):
            return rows[0][0]
    except sqlite3.Error:
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--native-root', required=True)
    args = parser.parse_args()
    email = administrator_email(args.native_root)
    if email:
        print(email)
