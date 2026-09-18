-- Logical migration marker for classroom schema version 1.
-- The executable, checksum-checked DDL lives in
-- classroom/app/classroom_service/database.py (SCHEMA), so the portable
-- runtime and the developer runner use exactly the same definition.
PRAGMA foreign_keys=ON;
