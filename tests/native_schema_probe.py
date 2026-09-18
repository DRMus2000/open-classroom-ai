import sqlite3,pathlib
root=pathlib.Path('dist/openwebui-classroom-review-windows-x64/data').resolve()
with sqlite3.connect((root/'openwebui/webui.db').as_uri()+'?mode=ro',uri=True) as db:
    print('tables',[(r[0],db.execute('SELECT COUNT(*) FROM "'+r[0].replace('"','""')+'"').fetchone()[0]) for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")])
    print('config_columns',db.execute('PRAGMA table_info(config)').fetchall())
with sqlite3.connect((root/'review/review.db').as_uri()+'?mode=ro',uri=True) as db:
    print('legacy_review_schema',db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall())
