# Classroom database migrations

`ClassroomDB` owns the schema and records a checksum in `schema_migrations`.
The first migration creates only classroom tables.  It does not stamp or
rewrite Open WebUI's `webui.db`; that database must be compared with the exact
0.11.2 baseline in an isolated copy before the cutover described in the plan.

Run `scripts/Migrate.ps1` with a copied classroom database, then run the
acceptance tests.  A checksum mismatch stops startup instead of silently
changing a live database.
