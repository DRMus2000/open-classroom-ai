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
It preserves attachment rows, native links, and operation copies. The v5 SQL
checksum is frozen. Startup runs a preflight for missing security_states on
attachment owners and native-file users; if it fails the migration rolls back
and the database stays on v4. Inspect or repair only enrolled students and
registered teachers with `scripts/Repair-V5Identities.ps1` (add `-Apply` after
verifying). Do not delete attachments or invent login identities. Keep the
joint backup taken before the patch.
