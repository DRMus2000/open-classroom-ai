"""Transactional daily quota reservations, settlement, expiry, and adjustments."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import uuid

from .clock import iso, local_date_and_next_midnight
from .database import ClassroomDB, json_dumps
from .errors import ConflictError, ForbiddenError, NotFoundError, QuotaError, ValidationError


ACTIVE_STATUSES = ("pending", "approved_queued", "generating")


class QuotaManager:
    def __init__(self, db: ClassroomDB, *, timezone_name: str = "UTC", timezone_revision: int = 1,
                 now_fn=None):
        self.db = db
        self.timezone_name = timezone_name
        self.timezone_revision = timezone_revision
        self.now_fn = now_fn

    def now(self) -> datetime:
        return self.now_fn() if self.now_fn else datetime.now().astimezone()

    def day_info(self, when: datetime | None = None) -> tuple[str, str]:
        current = when or self.now()
        date_text, next_midnight = local_date_and_next_midnight(current, self.timezone_name)
        return date_text, iso(next_midnight)

    def ensure_bucket_tx(self, db, user_id: str, quota_date: str, now_text: str):
        student = db.execute("SELECT * FROM students WHERE user_id=?", (user_id,)).fetchone()
        if not student:
            raise NotFoundError("student is not enrolled")
        db.execute(
            """INSERT OR IGNORE INTO daily_quotas
            (user_id,quota_date,timezone_id,timezone_revision,base_limit,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)""",
            (user_id, quota_date, self.timezone_name, self.timezone_revision,
             int(student["default_daily_limit"]), now_text, now_text),
        )
        return db.execute("SELECT * FROM daily_quotas WHERE user_id=? AND quota_date=?", (user_id, quota_date)).fetchone()

    @staticmethod
    def quota_dict(row) -> dict:
        available = int(row["base_limit"]) + int(row["adjustment"]) - int(row["used"]) - int(row["reserved"])
        return {
            "user_id": row["user_id"], "date": row["quota_date"], "timezone": row["timezone_id"],
            "base": int(row["base_limit"]), "adjustment": int(row["adjustment"]),
            "used": int(row["used"]), "reserved": int(row["reserved"]),
            "available": available, "version": int(row["version"]),
        }

    def read(self, user_id: str, when: datetime | None = None) -> dict:
        date_text, _ = self.day_info(when)
        now_text = iso(when or self.now())
        with self.db.transaction() as db:
            row = self.ensure_bucket_tx(db, user_id, date_text, now_text)
            return self.quota_dict(row)

    def reserve_tx(self, db, user_id: str, *, quota_date: str, now_text: str,
                   request_id: str, actor_id: str = "student") -> dict:
        row = self.ensure_bucket_tx(db, user_id, quota_date, now_text)
        if int(row["base_limit"]) + int(row["adjustment"]) - int(row["used"]) - int(row["reserved"]) < 1:
            raise QuotaError("今日可用次数不足")
        active = db.execute(
            "SELECT id FROM review_requests WHERE user_id=? AND status IN (?,?,?) LIMIT 1",
            (user_id, *ACTIVE_STATUSES),
        ).fetchone()
        if active:
            raise ConflictError("该学生已有活动请求", code="ACTIVE_REQUEST_EXISTS", request_id=active[0])
        before = self.quota_dict(row)
        db.execute(
            "UPDATE daily_quotas SET reserved=reserved+1,version=version+1,updated_at=? WHERE user_id=? AND quota_date=?",
            (now_text, user_id, quota_date),
        )
        after = self.quota_dict(db.execute("SELECT * FROM daily_quotas WHERE user_id=? AND quota_date=?", (user_id, quota_date)).fetchone())
        db.execute(
            """INSERT INTO quota_ledger
            (id,user_id,quota_date,request_id,kind,delta_reserved,delta_used,delta_adjustment,actor_id,reason,operation_key,before_json,after_json,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uuid.uuid4().hex, user_id, quota_date, request_id, "reserve", 1, 0, 0, actor_id,
             "request reservation", f"reserve:{request_id}", json_dumps(before), json_dumps(after), now_text),
        )
        return after

    def settle_tx(self, db, request_row, *, kind: str, actor_id: str, reason: str, now_text: str) -> dict:
        if kind not in {"settle_consumed", "settle_released"}:
            raise ValidationError("invalid settlement kind")
        request_id = request_row["id"]
        existing = db.execute("SELECT * FROM quota_ledger WHERE request_id=? AND kind IN ('settle_consumed','settle_released')", (request_id,)).fetchone()
        if existing:
            quota = db.execute("SELECT * FROM daily_quotas WHERE user_id=? AND quota_date=?", (request_row["user_id"], request_row["quota_date"])).fetchone()
            return self.quota_dict(quota)
        quota = db.execute("SELECT * FROM daily_quotas WHERE user_id=? AND quota_date=?", (request_row["user_id"], request_row["quota_date"])).fetchone()
        if not quota:
            raise RuntimeError("request quota bucket is missing")
        before = self.quota_dict(quota)
        consume = 1 if kind == "settle_consumed" else 0
        if int(quota["reserved"]) < 1:
            raise ConflictError("request has no open quota reservation", code="RESERVATION_MISSING", request_id=request_id)
        db.execute(
            "UPDATE daily_quotas SET reserved=reserved-1,used=used+?,version=version+1,updated_at=? WHERE user_id=? AND quota_date=?",
            (consume, now_text, request_row["user_id"], request_row["quota_date"]),
        )
        after = self.quota_dict(db.execute("SELECT * FROM daily_quotas WHERE user_id=? AND quota_date=?", (request_row["user_id"], request_row["quota_date"])).fetchone())
        db.execute(
            """INSERT INTO quota_ledger
            (id,user_id,quota_date,request_id,kind,delta_reserved,delta_used,delta_adjustment,actor_id,reason,operation_key,before_json,after_json,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uuid.uuid4().hex, request_row["user_id"], request_row["quota_date"], request_id, kind,
             -1, consume, 0, actor_id, reason, f"{kind}:{request_id}", json_dumps(before), json_dumps(after), now_text),
        )
        return after

    def adjust_many(self, user_ids: list[str], *, delta: int, actor_id: str, reason: str,
                    expected_versions: dict[str, int] | None = None,
                    when: datetime | None = None, operation_key: str | None = None,
                    requested_date: str | None = None, require_versions: bool = False) -> dict:
        if not isinstance(user_ids, list) or not user_ids or len(user_ids) > 30 or any(not isinstance(value, str) or not value for value in user_ids):
            raise ValidationError("select between one and thirty students")
        if type(delta) is not int or delta == 0 or abs(delta) > 100:
            raise ValidationError("adjustment must be a non-zero integer between -100 and 100")
        if expected_versions is None:
            expected_versions = {}
        if not isinstance(expected_versions, dict) or any(not isinstance(key, str) or not isinstance(value, int) for key, value in expected_versions.items()):
            raise ValidationError("expected_versions must be an object of integer versions")
        if not isinstance(reason, str) or len(reason) > 500:
            raise ValidationError("adjustment reason is invalid")
        normalized_ids = list(dict.fromkeys(user_ids))
        current_date, _ = self.day_info(when)
        date_text = requested_date or current_date
        if require_versions and set(expected_versions) != set(normalized_ids):
            raise ValidationError("preview versions are required for every selected student")
        now_text = iso(when or self.now())
        operation_key = operation_key or uuid.uuid4().hex
        if not isinstance(operation_key, str) or not operation_key.strip() or len(operation_key) > 200:
            raise ValidationError("operation_key must be a non-empty string")
        request_hash = hashlib.sha256(json.dumps({
            "actor_id": actor_id,
            "date": date_text,
            "delta": delta,
            "expected_versions": {key: expected_versions[key] for key in sorted(expected_versions)},
            "reason": reason,
            "user_ids": normalized_ids,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        with self.db.transaction() as db:
            scope = "quota-adjust:" + actor_id
            prior = db.execute("SELECT request_hash,result_json FROM idempotency_keys WHERE scope IN (?,?) AND key=?", (scope, "quota-adjust", operation_key)).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise ConflictError("同一调整标识对应了不同内容", code="IDEMPOTENCY_PAYLOAD_CONFLICT")
                return __import__("json").loads(prior["result_json"])
            if date_text != current_date:
                raise ConflictError("额度日期已变化，请重新预览", code="QUOTA_DATE_CONFLICT")
            rows = []
            for user_id in normalized_ids:
                row = self.ensure_bucket_tx(db, user_id, date_text, now_text)
                if user_id in expected_versions and int(row["version"]) != int(expected_versions[user_id]):
                    raise ConflictError("额度页面已过期，请重新预览", code="QUOTA_VERSION_CONFLICT")
                available = int(row["base_limit"]) + int(row["adjustment"]) - int(row["used"]) - int(row["reserved"])
                if available + delta < 0:
                    raise ValidationError("减少后不能低于已使用或已预留次数", code="QUOTA_ADJUSTMENT_INVALID")
                rows.append((user_id, row, self.quota_dict(row)))
            batch_id = uuid.uuid4().hex
            result_rows = []
            for user_id, _, before in rows:
                db.execute("UPDATE daily_quotas SET adjustment=adjustment+?,version=version+1,updated_at=? WHERE user_id=? AND quota_date=?", (delta, now_text, user_id, date_text))
                after = self.quota_dict(db.execute("SELECT * FROM daily_quotas WHERE user_id=? AND quota_date=?", (user_id, date_text)).fetchone())
                db.execute(
                    """INSERT INTO quota_ledger
                    (id,user_id,quota_date,kind,delta_reserved,delta_used,delta_adjustment,actor_id,reason,operation_key,batch_id,before_json,after_json,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (uuid.uuid4().hex, user_id, date_text, "teacher_adjust", 0, 0, delta, actor_id, reason, operation_key, batch_id, json_dumps(before), json_dumps(after), now_text),
                )
                result_rows.append({"user_id": user_id, "before": before, "after": after})
            result = {"batch_id": batch_id, "date": date_text, "delta": delta, "rows": result_rows}
            db.execute("INSERT INTO idempotency_keys(scope,key,request_hash,result_json,created_at) VALUES(?,?,?,?,?)", (scope, operation_key, request_hash, json_dumps(result), now_text))
            db.execute("INSERT INTO teacher_actions(id,actor_id,action,target_ids_json,result_json,created_at,operation_key) VALUES(?,?,?,?,?,?,?)", (uuid.uuid4().hex, actor_id, "quota_adjust", json_dumps(normalized_ids), json_dumps(result), now_text, operation_key))
            return result

    def expire_pending(self, *, when: datetime | None = None) -> int:
        current = when or self.now()
        now_text = iso(current)
        count = 0
        with self.db.transaction() as db:
            rows = db.execute("SELECT * FROM review_requests WHERE status='pending' AND expires_at<=? ORDER BY expires_at,id", (now_text,)).fetchall()
            for row in rows:
                updated = db.execute("UPDATE review_requests SET status='expired',version=version+1,reservation_state='released',finished_at=?,updated_at=?,charge_reason='pending request crossed local day' WHERE id=? AND status='pending'", (now_text, now_text, row["id"]))
                if updated.rowcount:
                    self.settle_tx(db, row, kind="settle_released", actor_id="system", reason="pending request expired", now_text=now_text)
                    count += 1
        return count
