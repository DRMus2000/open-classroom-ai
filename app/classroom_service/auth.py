"""Short-lived, revocable classroom sessions independent of Open WebUI JWT."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets

from .clock import iso, parse_iso
from .database import ClassroomDB
from .errors import AuthenticationError, ForbiddenError


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class Principal:
    def __init__(self, user_id: str, role: str, session_fingerprint: str, must_change_password: bool = False):
        self.user_id = user_id
        self.role = role
        self.session_fingerprint = session_fingerprint
        self.must_change_password = must_change_password

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"


class SessionManager:
    def __init__(self, db: ClassroomDB, secret: bytes | None = None, *, clock=None, max_hours: int = 12):
        self.db = db
        self.secret = secret or secrets.token_bytes(32)
        if len(self.secret) < 32:
            raise ValueError("session secret must contain at least 32 bytes")
        self.clock = clock
        self.max_hours = max_hours

    def now(self) -> datetime:
        return self.clock.now() if self.clock else datetime.now(timezone.utc)

    def _sign(self, encoded_payload: str) -> str:
        return _b64(hmac.new(self.secret, encoded_payload.encode("ascii"), hashlib.sha256).digest())

    def issue(self, user_id: str, *, role: str = "student", expires_hours: int | None = None) -> str:
        now = self.now()
        with self.db.transaction() as db:
            state = db.execute("SELECT * FROM security_states WHERE user_id=?", (user_id,)).fetchone()
            if not state:
                raise AuthenticationError("classroom security state is not initialized")
            hours = max(1, min(int(expires_hours or self.max_hours), self.max_hours))
            exp = now + timedelta(hours=hours)
            payload = {"v": 1, "uid": user_id, "role": role, "iat": iso(now), "exp": iso(exp), "epoch": int(state["auth_epoch"]), "nonce": secrets.token_urlsafe(18)}
            encoded = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
            token = f"v1.{encoded}.{self._sign(encoded)}"
            fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
            db.execute(
                "INSERT INTO classroom_sessions(token_fingerprint,user_id,epoch,issued_at,expires_at,last_seen_at) VALUES(?,?,?,?,?,?)",
                (fingerprint, user_id, payload["epoch"], payload["iat"], payload["exp"], payload["iat"]),
            )
            return token

    def validate(self, token: str, *, require_generation: bool = False) -> Principal:
        try:
            parts = token.split(".")
            if len(parts) != 3 or parts[0] != "v1":
                raise ValueError
            encoded, signature = parts[1], parts[2]
            if not hmac.compare_digest(signature, self._sign(encoded)):
                raise ValueError
            payload = json.loads(_unb64(encoded).decode("utf-8"))
            if payload.get("v") != 1 or not payload.get("uid") or payload.get("role") not in {"student", "teacher"}:
                raise ValueError
            now = self.now()
            if now >= parse_iso(payload["exp"]):
                raise ValueError
        except Exception as exc:
            raise AuthenticationError("invalid or expired classroom session") from exc
        fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now_text = iso(now)
        with self.db.transaction() as db:
            session = db.execute("SELECT * FROM classroom_sessions WHERE token_fingerprint=?", (fingerprint,)).fetchone()
            state = db.execute("SELECT * FROM security_states WHERE user_id=?", (payload["uid"],)).fetchone()
            if not session or not state or session["revoked_at"] or int(session["epoch"]) != int(state["auth_epoch"]) or int(payload["epoch"]) != int(state["auth_epoch"]):
                raise AuthenticationError("classroom session has been revoked")
            if now >= parse_iso(session["expires_at"]):
                raise AuthenticationError("classroom session has expired")
            db.execute("UPDATE classroom_sessions SET last_seen_at=? WHERE token_fingerprint=?", (now_text, fingerprint))
            principal = Principal(payload["uid"], payload["role"], fingerprint, bool(state["must_change_password"]))
            if require_generation and principal.must_change_password:
                raise ForbiddenError("首次登录必须修改密码", code="PASSWORD_CHANGE_REQUIRED", status=428)
            return principal

    def revoke_user(self, user_id: str, *, actor_id: str = "system") -> None:
        now_text = iso(self.now())
        with self.db.transaction() as db:
            state = db.execute("SELECT * FROM security_states WHERE user_id=?", (user_id,)).fetchone()
            if not state:
                raise AuthenticationError("classroom security state is not initialized")
            epoch = int(state["auth_epoch"]) + 1
            db.execute("UPDATE security_states SET auth_epoch=?,updated_at=?,reset_by=? WHERE user_id=?", (epoch, now_text, actor_id, user_id))
            db.execute("UPDATE classroom_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now_text, user_id))

    def session_issued(self, user_id: str, fingerprint: str, *, native_expires_at: str,
                       expected_epoch: int) -> None:
        """Called only by the signed, successful native password-login hook."""
        if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
            raise AuthenticationError("invalid native token fingerprint")
        now = self.now()
        exp = min(parse_iso(native_expires_at), now + timedelta(hours=self.max_hours))
        if exp <= now:
            raise AuthenticationError("native session has expired")
        with self.db.transaction() as db:
            state = db.execute("SELECT * FROM security_states WHERE user_id=?", (user_id,)).fetchone()
            if not state or state["auth_epoch"] != expected_epoch:
                raise AuthenticationError("security state changed during login; sign in again")
            existing = db.execute("SELECT * FROM classroom_sessions WHERE token_fingerprint=?", (fingerprint,)).fetchone()
            if existing:
                if existing["epoch"] != expected_epoch or existing["revoked_at"]:
                    raise AuthenticationError("this native token has already been revoked")
                return
            db.execute("INSERT INTO classroom_sessions(token_fingerprint,user_id,epoch,issued_at,expires_at,last_seen_at) VALUES(?,?,?,?,?,?)",
                       (fingerprint, user_id, expected_epoch, iso(now), iso(exp), iso(now)))

    def validate_native(self, user_id: str, fingerprint: str, *, role: str,
                        require_generation: bool = False) -> Principal:
        now = self.now()
        with self.db.transaction() as db:
            state = db.execute("SELECT * FROM security_states WHERE user_id=?", (user_id,)).fetchone()
            session = db.execute("SELECT * FROM classroom_sessions WHERE token_fingerprint=?", (fingerprint,)).fetchone()
            if (not state or not session or session["user_id"] != user_id or session["revoked_at"]
                    or session["epoch"] != state["auth_epoch"] or now >= parse_iso(session["expires_at"])):
                raise AuthenticationError("课堂会话无效或已撤销，请重新登录")
            if role not in {"admin", "user"}:
                raise ForbiddenError("native account is not active")
            restricted = bool(state["must_change_password"] or state["credential_operation_state"] != "ready")
            if role != "admin":
                student = db.execute("SELECT * FROM students WHERE user_id=?", (user_id,)).fetchone()
                if not student or student["enrollment_state"] != "active":
                    raise ForbiddenError("学生不在有效课堂名册中")
                if require_generation and not student["ai_enabled"]:
                    raise ForbiddenError("该学生的 AI 权限已暂停")
                if require_generation and restricted:
                    raise ForbiddenError("首次登录必须修改密码", code="PASSWORD_CHANGE_REQUIRED", status=428)
            db.execute("UPDATE classroom_sessions SET last_seen_at=? WHERE token_fingerprint=?", (iso(now), fingerprint))
            return Principal(user_id, "teacher" if role == "admin" else "student", fingerprint, restricted)

    def register_native_token(self, user_id: str, token: str) -> None:
        # Compatibility callers may validate, but can never enroll an old JWT.
        self.validate_native(user_id, hashlib.sha256(token.encode()).hexdigest(), role="user")

    def begin_security_operation(self, user_id: str, *, actor_id: str) -> int:
        with self.db.transaction() as db:
            state = db.execute("SELECT * FROM security_states WHERE user_id=?", (user_id,)).fetchone()
            if not state:
                raise AuthenticationError("security state is not initialized")
            epoch = state["auth_epoch"] + 1
            now = iso(self.now())
            db.execute("UPDATE security_states SET credential_operation_state='reset_in_progress',must_change_password=1,auth_epoch=?,updated_at=?,reset_by=? WHERE user_id=?", (epoch, now, actor_id, user_id))
            db.execute("UPDATE classroom_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now, user_id))
            return epoch

    def finish_security_operation(self, user_id: str, epoch: int, *, success: bool,
                                  must_change: bool, actor_id: str) -> None:
        with self.db.transaction() as db:
            now = iso(self.now())
            changed = db.execute("UPDATE security_states SET credential_operation_state=?,must_change_password=?,password_changed_at=?,updated_at=? WHERE user_id=? AND auth_epoch=?", ("ready" if success else "reset_failed", int(must_change or not success), now if success else None, now, user_id, epoch))
            if not changed.rowcount:
                raise AuthenticationError("a newer security operation superseded this result")
            db.execute("INSERT INTO teacher_actions(id,actor_id,action,target_ids_json,result_json,created_at) VALUES(?,?,?,?,?,?)", (secrets.token_hex(16), actor_id, "security_operation", json.dumps([user_id]), json.dumps({"epoch": epoch, "success": success, "must_change_password": must_change or not success}), now))

    def set_password_state(self, user_id: str, *, must_change: bool, actor_id: str) -> None:
        now_text = iso(self.now())
        with self.db.transaction() as db:
            state = db.execute("SELECT * FROM security_states WHERE user_id=?", (user_id,)).fetchone()
            if not state:
                raise AuthenticationError("classroom security state is not initialized")
            epoch = int(state["auth_epoch"]) + 1
            db.execute(
                "UPDATE security_states SET must_change_password=?,auth_epoch=?,password_changed_at=?,reset_by=?,updated_at=?,credential_operation_state='ready' WHERE user_id=?",
                (1 if must_change else 0, epoch, now_text, actor_id, now_text, user_id),
            )
            db.execute("UPDATE classroom_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now_text, user_id))

    def cleanup(self) -> int:
        now_text = iso(self.now())
        with self.db.transaction() as db:
            result = db.execute("DELETE FROM classroom_sessions WHERE revoked_at IS NOT NULL OR expires_at<=?", (now_text,))
            return result.rowcount
