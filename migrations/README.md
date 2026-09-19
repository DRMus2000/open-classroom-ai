# Classroom database migrations

`ClassroomDB` owns the schema and records a checksum in `schema_migrations`.
The first migration creates only classroom tables.  It does not stamp or
rewrite Open WebUI's `webui.db`; that database must be compared with the exact
0.11.2 baseline in an isolated copy before the cutover described in the plan.

Run `scripts/Migrate.ps1` with a copied classroom database, then run the
acceptance tests.  A checksum mismatch stops startup instead of silently
changing a live database.

The 2.1.8 audit patch adds v5: attachment ownership references registered
security identities, allowing teachers to upload without student enrollment.
It preserves attachment rows, native links, and operation copies. Back up
offline before applying the patch; rollback requires the pre-upgrade backup
and matching old code, not just replacement of Python files.
