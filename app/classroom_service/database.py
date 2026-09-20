"""SQLite storage for the classroom state machine.

The schema is owned by this package.  Open WebUI's database is intentionally
not modified here; adapters use its supported APIs and pass immutable identity
and file snapshots into this database.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any, Iterator


SCHEMA_VERSION = 5


SCHEMA = r"""
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS classroom_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS students (
    user_id TEXT PRIMARY KEY,
    roster_name TEXT NOT NULL,
    login_identifier TEXT NOT NULL,
    default_daily_limit INTEGER NOT NULL DEFAULT 3 CHECK(default_daily_limit >= 0),
    ai_enabled INTEGER NOT NULL DEFAULT 1 CHECK(ai_enabled IN (0,1)),
    enrollment_state TEXT NOT NULL DEFAULT 'active'
        CHECK(enrollment_state IN ('provisioning','active','disabled','deleted_origin')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS security_states (
    user_id TEXT PRIMARY KEY,
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK(must_change_password IN (0,1)),
    credential_operation_state TEXT NOT NULL DEFAULT 'ready'
        CHECK(credential_operation_state IN ('ready','initializing','reset_in_progress','reset_failed')),
    auth_epoch INTEGER NOT NULL DEFAULT 0 CHECK(auth_epoch >= 0),
    password_changed_at TEXT,
    reset_by TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS classroom_sessions (
    token_fingerprint TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES security_states(user_id)
);

CREATE TABLE IF NOT EXISTS daily_quotas (
    user_id TEXT NOT NULL,
    quota_date TEXT NOT NULL,
    timezone_id TEXT NOT NULL,
    timezone_revision INTEGER NOT NULL,
    base_limit INTEGER NOT NULL CHECK(base_limit >= 0),
    adjustment INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0 CHECK(used >= 0),
    reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved >= 0),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, quota_date),
    FOREIGN KEY(user_id) REFERENCES students(user_id)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    request_id TEXT,
    kind TEXT NOT NULL CHECK(kind IN ('original','effective','context','response')),
    schema_version INTEGER NOT NULL,
    digest TEXT NOT NULL,
    payload_json TEXT,
    blob_ref TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL,
    request_id TEXT,
    source_file_id TEXT,
    original_filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    sha256 TEXT NOT NULL,
    blob_ref TEXT NOT NULL,
    normalized_ref TEXT,
    text_encoding TEXT,
    image_width INTEGER,
    image_height INTEGER,
    created_at TEXT NOT NULL,
    retention_class TEXT NOT NULL DEFAULT 'permanent'
        CHECK(retention_class IN ('temporary','permanent')),
    FOREIGN KEY(owner_user_id) REFERENCES students(user_id)
);

CREATE TABLE IF NOT EXISTS review_requests (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    client_operation_id TEXT NOT NULL,
    client_payload_digest TEXT NOT NULL,
    chat_id TEXT,
    user_message_id TEXT,
    assistant_message_id TEXT,
    parent_request_id TEXT,
    quota_date TEXT NOT NULL,
    timezone_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN (
        'pending','approved_queued','generating','completed','rejected',
        'cancelled_before_output','stopped_by_student_after_output',
        'interrupted','expired','interrupted_unknown'
    )),
    version INTEGER NOT NULL DEFAULT 1,
    original_snapshot_id TEXT NOT NULL,
    effective_snapshot_id TEXT,
    effective_digest TEXT,
    provider_profile_id TEXT NOT NULL,
    provider_profile_version INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    decided_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    decision_actor_id TEXT,
    decision_kind TEXT,
    decision_note TEXT,
    reservation_state TEXT NOT NULL DEFAULT 'open'
        CHECK(reservation_state IN ('open','released','consumed')),
    charge_units INTEGER NOT NULL DEFAULT 0 CHECK(charge_units IN (0,1)),
    charge_reason TEXT,
    error_code TEXT,
    interruption_source TEXT,
    output_text TEXT,
    visible_output_bytes INTEGER NOT NULL DEFAULT 0 CHECK(visible_output_bytes >= 0),
    legacy_id TEXT,
    legacy_status TEXT,
    provenance TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES students(user_id),
    FOREIGN KEY(original_snapshot_id) REFERENCES snapshots(id),
    FOREIGN KEY(effective_snapshot_id) REFERENCES snapshots(id)
);

CREATE TABLE IF NOT EXISTS execution_attempts (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    worker_instance_id TEXT NOT NULL,
    claim_token TEXT NOT NULL UNIQUE,
    claimed_at TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    dispatch_state TEXT NOT NULL CHECK(dispatch_state IN (
        'claimed','dispatching','dispatched_unknown','streaming','ended'
    )),
    dispatch_marked_at TEXT,
    first_output_at TEXT,
    ended_at TEXT,
    upstream_request_id TEXT,
    output_ref TEXT,
    finish_reason TEXT,
    termination_source TEXT,
    FOREIGN KEY(request_id) REFERENCES review_requests(id)
);

CREATE TABLE IF NOT EXISTS response_events (
    request_id TEXT NOT NULL,
    seq INTEGER NOT NULL CHECK(seq > 0),
    event_type TEXT NOT NULL CHECK(event_type IN ('started','delta','completed','error','stopped','interrupted')),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(request_id, seq),
    FOREIGN KEY(request_id) REFERENCES review_requests(id)
);

CREATE TABLE IF NOT EXISTS quota_ledger (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    quota_date TEXT NOT NULL,
    request_id TEXT,
    kind TEXT NOT NULL CHECK(kind IN ('reserve','settle_consumed','settle_released','teacher_adjust')),
    delta_reserved INTEGER NOT NULL DEFAULT 0,
    delta_used INTEGER NOT NULL DEFAULT 0,
    delta_adjustment INTEGER NOT NULL DEFAULT 0,
    actor_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    operation_key TEXT NOT NULL,
    batch_id TEXT,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES students(user_id),
    FOREIGN KEY(request_id) REFERENCES review_requests(id)
);

CREATE TABLE IF NOT EXISTS teacher_actions (
    id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target_ids_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    operation_key TEXT
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    scope TEXT NOT NULL,
    key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(scope, key)
);

CREATE TABLE IF NOT EXISTS account_imports (
    id TEXT PRIMARY KEY,
    teacher_id TEXT NOT NULL,
    source_digest TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('preview','committing','completed','partial','failed','expired')),
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_rows (
    batch_id TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    normalized_login TEXT NOT NULL,
    roster_name TEXT NOT NULL,
    status TEXT NOT NULL,
    user_id TEXT,
    error_code TEXT,
    PRIMARY KEY(batch_id, row_number),
    FOREIGN KEY(batch_id) REFERENCES account_imports(id)
);

CREATE INDEX IF NOT EXISTS idx_requests_status_submitted
    ON review_requests(status, submitted_at, id);
CREATE INDEX IF NOT EXISTS idx_requests_user_submitted
    ON review_requests(user_id, submitted_at, id);
CREATE INDEX IF NOT EXISTS idx_requests_pending_expiry
    ON review_requests(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_attachments_request
    ON attachments(request_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user
    ON classroom_sessions(user_id, revoked_at, expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_request_final_settlement
    ON quota_ledger(request_id)
    WHERE kind IN ('settle_consumed','settle_released');
"""


SCHEMA_V2 = r"""
ALTER TABLE review_requests ADD COLUMN delivered_seq INTEGER NOT NULL DEFAULT 0 CHECK(delivered_seq >= 0);
ALTER TABLE review_requests ADD COLUMN cancel_source TEXT;
ALTER TABLE review_requests ADD COLUMN cancel_requested_at TEXT;
CREATE UNIQUE INDEX uq_request_operation ON review_requests(user_id,client_operation_id);
CREATE UNIQUE INDEX uq_student_active_request ON review_requests(user_id)
    WHERE status IN ('pending','approved_queued','generating');
CREATE TRIGGER quota_bounds_insert BEFORE INSERT ON daily_quotas
WHEN NEW.reserved > 1 OR NEW.base_limit + NEW.adjustment < NEW.used + NEW.reserved
BEGIN SELECT RAISE(ABORT,'invalid quota balance'); END;
CREATE TRIGGER quota_bounds_update BEFORE UPDATE ON daily_quotas
WHEN NEW.reserved > 1 OR NEW.base_limit + NEW.adjustment < NEW.used + NEW.reserved
BEGIN SELECT RAISE(ABORT,'invalid quota balance'); END;
CREATE TABLE execution_deliveries (
    request_id TEXT NOT NULL REFERENCES review_requests(id),
    consumer_id TEXT NOT NULL,
    delivered_seq INTEGER NOT NULL DEFAULT 0,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY(request_id,consumer_id)
);
"""
SCHEMA_V3 = r"""
CREATE TABLE native_attachments (
    user_id TEXT NOT NULL REFERENCES students(user_id),
    native_file_id TEXT NOT NULL,
    attachment_id TEXT NOT NULL REFERENCES attachments(id),
    PRIMARY KEY(user_id,native_file_id)
);
CREATE TABLE native_attachment_copies (
    user_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    native_file_id TEXT NOT NULL,
    attachment_id TEXT NOT NULL REFERENCES attachments(id),
    PRIMARY KEY(user_id,operation_id,native_file_id)
);
CREATE TABLE legacy_records (
    source TEXT NOT NULL,
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    user_id TEXT,
    payload_json TEXT NOT NULL,
    source_digest TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    PRIMARY KEY(source,record_type,record_id)
);
"""
SCHEMA_V4 = r"""
ALTER TABLE review_requests ADD COLUMN review_channel TEXT NOT NULL DEFAULT 'teacher';
CREATE TABLE ai_audit_turns (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    question_excerpt TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    raw_response TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(request_id) REFERENCES review_requests(id),
    FOREIGN KEY(student_id) REFERENCES students(user_id)
);
CREATE INDEX idx_ai_audit_created ON ai_audit_turns(created_at DESC, id DESC);
CREATE INDEX idx_requests_review_channel ON review_requests(status, review_channel, submitted_at);
"""
SCHEMA_V5 = r"""
CREATE TABLE attachments_v5 (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL REFERENCES security_states(user_id),
    request_id TEXT,
    source_file_id TEXT,
    original_filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    sha256 TEXT NOT NULL,
    blob_ref TEXT NOT NULL,
    normalized_ref TEXT,
    text_encoding TEXT,
    image_width INTEGER,
    image_height INTEGER,
    created_at TEXT NOT NULL,
    retention_class TEXT NOT NULL DEFAULT 'permanent'
        CHECK(retention_class IN ('temporary','permanent'))
);
INSERT INTO attachments_v5 SELECT * FROM attachments;
CREATE TABLE native_attachments_v5 (
    user_id TEXT NOT NULL REFERENCES security_states(user_id),
    native_file_id TEXT NOT NULL,
    attachment_id TEXT NOT NULL REFERENCES attachments_v5(id),
    PRIMARY KEY(user_id,native_file_id)
);
INSERT INTO native_attachments_v5 SELECT * FROM native_attachments;
CREATE TABLE native_attachment_copies_v5 (
    user_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    native_file_id TEXT NOT NULL,
    attachment_id TEXT NOT NULL REFERENCES attachments_v5(id),
    PRIMARY KEY(user_id,operation_id,native_file_id)
);
INSERT INTO native_attachment_copies_v5 SELECT * FROM native_attachment_copies;
DROP TABLE native_attachment_copies;
DROP TABLE native_attachments;
DROP TABLE attachments;
ALTER TABLE attachments_v5 RENAME TO attachments;
ALTER TABLE native_attachments_v5 RENAME TO native_attachments;
ALTER TABLE native_attachment_copies_v5 RENAME TO native_attachment_copies;
CREATE INDEX idx_attachments_request ON attachments(request_id, created_at);
"""
MIGRATIONS = {1: SCHEMA, 2: SCHEMA_V2, 3: SCHEMA_V3, 4: SCHEMA_V4, 5: SCHEMA_V5}


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


class ClassroomDB:
    """A small connection-per-operation SQLite wrapper.

    The wrapper configures foreign keys and a busy timeout for every connection
    and exposes explicit short write transactions.  No network or provider
    operation is ever run while a transaction is open.
    """

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self._keeper: sqlite3.Connection | None = None
        if self.path == ":memory:":
            self._uri = f"file:classroom-{secrets.token_hex(8)}?mode=memory&cache=shared"
            # A shared in-memory database disappears when its last connection
            # closes.  Keep one connection alive while the DB object is used.
            self._keeper = sqlite3.connect(self._uri, uri=True, isolation_level=None)
            self._keeper.row_factory = sqlite3.Row
        else:
            self._uri = self.path
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._uri, uri=self.path == ":memory:", timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        if self.path != ":memory:":
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
        return db

    def initialize(self) -> None:
        from hashlib import sha256
        checksums = {version: sha256(script.encode("utf-8")).hexdigest() for version, script in MIGRATIONS.items()}
        if self.path != ":memory:" and Path(self.path).exists():
            check = sqlite3.connect(Path(self.path).resolve().as_uri() + "?mode=ro", uri=True)
            try:
                tables = {r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if tables:
                    if "schema_migrations" not in tables:
                        raise RuntimeError("unrecognized classroom database; explicit migration required")
                    revisions = check.execute("SELECT version,checksum FROM schema_migrations ORDER BY version").fetchall()
                    if (not revisions or [v for v, _ in revisions] != list(range(1, len(revisions) + 1))
                            or any(checksums.get(v) != h for v, h in revisions)):
                        raise RuntimeError("classroom schema checksum mismatch; migration is required")
                    reference = sqlite3.connect(':memory:')
                    try:
                        for version, _ in revisions:
                            reference.executescript(MIGRATIONS[version])
                        query = "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
                        if check.execute(query).fetchall() != reference.execute(query).fetchall():
                            raise RuntimeError('classroom schema objects were modified; repair from a verified backup')
                    finally:
                        reference.close()
            finally:
                check.close()
        db = self.connect()
        try:
            from datetime import datetime, timezone
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
            applied = dict(db.execute("SELECT version,checksum FROM schema_migrations")) if exists else {}
            for version, script in MIGRATIONS.items():
                if version in applied:
                    if applied[version] != checksums[version]:
                        raise RuntimeError("classroom migration checksum mismatch")
                    continue
                if version == 5:
                    from .schema_v5 import preflight_schema_v5
                    preflight_schema_v5(db)
                try:
                    db.executescript("BEGIN IMMEDIATE;\n" + script)
                    db.execute("INSERT INTO schema_migrations(version,checksum,applied_at) VALUES(?,?,?)",
                               (version, checksums[version], datetime.now(timezone.utc).isoformat()))
                    db.execute("COMMIT")
                except Exception:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    raise
        finally:
            db.close()

    def close(self) -> None:
        if self._keeper is not None:
            self._keeper.close()
            self._keeper = None

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        db = self.connect()
        try:
            begin_sql = "BEGIN IMMEDIATE" if immediate else "BEGIN"
            last_error = None
            for attempt in range(80):
                try:
                    db.execute(begin_sql)
                    last_error = None
                    break
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                        raise
                    last_error = exc
                    time.sleep(min(0.01 * (attempt + 1), 0.2))
            if last_error is not None:
                raise last_error
            yield db
            for attempt in range(80):
                try:
                    db.execute("COMMIT")
                    break
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                        raise
                    if attempt == 79:
                        raise
                    time.sleep(min(0.01 * (attempt + 1), 0.2))
        except Exception:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

    def query_one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        db = self.connect()
        try:
            return db.execute(sql, params).fetchone()
        finally:
            db.close()

    def query_all(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        db = self.connect()
        try:
            return db.execute(sql, params).fetchall()
        finally:
            db.close()
