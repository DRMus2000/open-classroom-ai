"""Safe roster CSV preview/commit and password-reset orchestration."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import secrets
from typing import Protocol
import uuid
import threading

from .clock import iso
from .database import json_dumps
from .errors import ConflictError, ForbiddenError, ValidationError
from .service import ClassroomService


REQUIRED_HEADERS = {"Name", "Email", "Password", "Role"}


class NativeAccountAdapter(Protocol):
    def create_user(self, *, name: str, email: str, password: str, role: str) -> str: ...
    def reset_password(self, *, user_id: str, password: str) -> None: ...
    def change_password(self, *, user_id: str, current_password: str, new_password: str) -> None: ...
    def delete_user(self, *, user_id: str) -> None: ...


class OpenWebUIHTTPAccountAdapter:
    """Small adapter for the exact-version native account endpoints.

    The classroom service never writes Open WebUI's auth tables.  A request
    carrying the verified teacher token creates this adapter for one import
    commit, and the adapter calls the bundled admin APIs.  Keeping the token
    request-scoped also avoids a long-lived teacher credential in the service.
    """

    manages_security = True

    def __init__(self, base_url: str, token: str, *, timeout: float = 15.0):
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            raise ValidationError("native account adapter URL is invalid")
        if not isinstance(token, str) or not token:
            raise ValidationError("native account adapter token is required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.base_url + path, data=raw, method=method)
        request.add_header("Accept", "application/json")
        request.add_header("Authorization", f"Bearer {self.token}")
        if raw is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                value = json.loads(body) if body else {}
                if value is False or value is None:
                    raise ValidationError("Open WebUI rejected the account operation", code="NATIVE_ACCOUNT_OPERATION_FAILED")
                return value
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body).get("detail", body[:300])
            except (TypeError, ValueError):
                detail = body[:300]
            raise ValidationError(f"Open WebUI account operation failed: {detail}", code="NATIVE_ACCOUNT_OPERATION_FAILED", status=400) from exc
        except OSError as exc:
            raise ValidationError("Open WebUI account endpoint is unavailable", code="NATIVE_ACCOUNT_UNAVAILABLE", status=503) from exc

    def create_user(self, *, name: str, email: str, password: str, role: str) -> str:
        if role != "user":
            raise ValidationError("only the student user role may be imported")
        result = self._request("POST", "/api/v1/auths/add", {"name": name, "email": email, "password": password, "role": role})
        user_id = result.get("id")
        if not isinstance(user_id, str) or not user_id:
            raise ValidationError("Open WebUI did not return the created user ID", code="NATIVE_ACCOUNT_INVALID_RESPONSE")
        return user_id

    def find_user(self, email: str):
        value = self._request("GET", "/api/v1/users/?query=" + urllib.parse.quote(email, safe=""))
        users = value.get("users", []) if isinstance(value, dict) else []
        return next((u["id"] for u in users if u.get("email", "").casefold() == email.casefold()), None)

    def reset_password(self, *, user_id: str, password: str) -> None:
        self._request("POST", f"/api/v1/users/{urllib.parse.quote(user_id, safe='')}/update", {"password": password})

    def delete_user(self, *, user_id: str) -> None:
        self._request("DELETE", f"/api/v1/users/{urllib.parse.quote(user_id, safe='')}")

    def change_password(self, *, user_id: str, current_password: str, new_password: str) -> None:
        self._request("POST", "/api/v1/auths/update/password", {"password": current_password, "new_password": new_password})


class MemoryAccountAdapter:
    """A test adapter that models the supported Open WebUI admin APIs."""
    def __init__(self):
        self.users: dict[str, dict] = {}
        self.reset_calls: list[str] = []

    def create_user(self, *, name: str, email: str, password: str, role: str) -> str:
        if role != "user":
            raise ValidationError("only the student user role may be imported")
        key = email.casefold()
        if any(v["email"].casefold() == key for v in self.users.values()):
            raise ConflictError("email already exists", code="ACCOUNT_EXISTS")
        user_id = uuid.uuid4().hex
        self.users[user_id] = {"name": name, "email": email, "password": password, "role": role}
        return user_id

    def reset_password(self, *, user_id: str, password: str) -> None:
        if user_id not in self.users:
            raise ValidationError("native user not found")
        self.users[user_id]["password"] = password
        self.reset_calls.append(user_id)

    def delete_user(self, *, user_id: str) -> None:
        self.users.pop(user_id, None)

    def find_user(self, email: str):
        return next((uid for uid, u in self.users.items() if u["email"].casefold() == email.casefold()), None)

    def change_password(self, *, user_id: str, current_password: str, new_password: str) -> None:
        if user_id not in self.users or self.users[user_id]["password"] != current_password:
            raise ValidationError("current password is incorrect")
        self.users[user_id]["password"] = new_password


@dataclass
class PreviewRow:
    row_number: int
    name: str
    email: str
    password: str
    role: str
    error_code: str | None = None


@dataclass
class ImportPreview:
    batch_id: str
    teacher_id: str
    source_digest: str
    rows: list[PreviewRow]
    expires_at: object


class AccountProvisioner:
    def __init__(self, service: ClassroomService, adapter: NativeAccountAdapter | None = None, *, preview_minutes: int = 10):
        self.service = service
        self.adapter = adapter
        self.preview_minutes = preview_minutes
        self._previews: dict[str, ImportPreview] = {}
        self._commit_lock = threading.Lock()

    def _forget_preview(self, batch_id: str) -> None:
        preview = self._previews.pop(batch_id, None)
        if preview is None:
            return
        for row in preview.rows:
            row.password = ''

    def _purge_expired_previews(self) -> None:
        now = self.service.now()
        expired = [batch_id for batch_id, preview in self._previews.items() if now >= preview.expires_at]
        if not expired:
            return
        with self.service.db.transaction() as db:
            for batch_id in expired:
                db.execute("UPDATE account_imports SET status='expired',updated_at=? WHERE id=? AND status='preview'", (iso(now), batch_id))
                self._forget_preview(batch_id)

    def preview(self, teacher_id: str, content: str | bytes) -> dict:
        self._purge_expired_previews()
        if isinstance(content, str):
            raw = content.encode("utf-8-sig")
        elif isinstance(content, bytes):
            raw = content
        else:
            raise ValidationError("CSV content must be text or bytes")
        digest = hashlib.sha256(raw).hexdigest()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError("roster CSV must be UTF-8") from exc
        try:
            reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
            headers = set(reader.fieldnames or [])
        except csv.Error as exc:
            raise ValidationError("invalid CSV") from exc
        if headers != REQUIRED_HEADERS:
            raise ValidationError("CSV headers must be exactly Name,Email,Password,Role")
        rows: list[PreviewRow] = []
        emails: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            if row.get(None):
                raise ValidationError(f"CSV row {row_number} has extra columns")
            name = (row.get("Name") or "").strip()
            email = (row.get("Email") or "").strip()
            password = row.get("Password") or ""
            role = (row.get("Role") or "").strip().lower()
            error = None
            if not name or len(name) > 120:
                error = "INVALID_NAME"
            elif len(email) > 320 or not (email.lower().endswith('@localhost') or re.match(r'[^@]+@[^@]+\.[^@]+', email)):
                error = "INVALID_EMAIL"
            elif email.casefold() in emails:
                error = "DUPLICATE_EMAIL"
            elif len(password) < 8:
                error = "WEAK_INITIAL_PASSWORD"
            elif role != "user":
                error = "ROLE_NOT_ALLOWED"
            if error is None:
                emails.add(email.casefold())
            rows.append(PreviewRow(row_number, name, email, password, role, error))
        if not rows or len(rows) > 30:
            raise ValidationError("roster must contain between one and thirty rows")
        now = self.service.now()
        preview = ImportPreview(uuid.uuid4().hex, teacher_id, digest, rows, now + timedelta(minutes=self.preview_minutes))
        prior = self.service.db.query_one("SELECT id FROM account_imports WHERE teacher_id=? AND source_digest=? AND status IN ('committing','partial','completed') ORDER BY created_at DESC LIMIT 1", (teacher_id, digest))
        if prior:
            preview.batch_id = prior[0]
            self._previews[preview.batch_id] = preview
            return {"batch_id": preview.batch_id, "source_digest": digest, "expires_at": iso(preview.expires_at), "resuming": True,
                    "rows": [{"row_number": r.row_number, "name": r.name, "email": r.email, "role": r.role, "error_code": r.error_code} for r in rows]}
        self._previews[preview.batch_id] = preview
        now_text = iso(now)
        with self.service.db.transaction() as db:
            db.execute("INSERT INTO account_imports(id,teacher_id,source_digest,status,summary_json,created_at,expires_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (preview.batch_id, teacher_id, digest, "preview", json_dumps({"total": len(rows), "valid": sum(r.error_code is None for r in rows)}), now_text, iso(preview.expires_at), now_text))
            for row in rows:
                db.execute("INSERT INTO import_rows(batch_id,row_number,normalized_login,roster_name,status,error_code) VALUES(?,?,?,?,?,?)", (preview.batch_id, row.row_number, row.email.casefold(), row.name, "valid" if row.error_code is None else "invalid", row.error_code))
        return {"batch_id": preview.batch_id, "source_digest": digest, "expires_at": iso(preview.expires_at), "rows": [{"row_number": r.row_number, "name": r.name, "email": r.email, "role": r.role, "error_code": r.error_code} for r in rows]}

    def commit(self, teacher_id: str, batch_id: str, *, adapter: NativeAccountAdapter | None = None) -> dict:
        with self._commit_lock:
            return self._commit(teacher_id, batch_id, adapter=adapter)

    def _commit(self, teacher_id: str, batch_id: str, *, adapter=None) -> dict:
        previous = self.service.db.query_one("SELECT * FROM account_imports WHERE id=? AND teacher_id=?", (batch_id, teacher_id))
        if previous and previous["status"] == "completed":
            if not json.loads(previous["summary_json"]).get('results'):
                raise ValidationError('名册没有可导入的有效行，请检查预览中的错误并修改 CSV。', code='NO_VALID_IMPORT_ROWS')
            self._forget_preview(batch_id)
            return {"batch_id": batch_id, "status": "completed", "results": json.loads(previous["summary_json"])["results"]}
        self._purge_expired_previews()
        preview = self._previews.get(batch_id)
        if not preview or preview.teacher_id != teacher_id:
            raise ValidationError("import preview is missing or belongs to another teacher")
        if self.service.now() >= preview.expires_at:
            raise ValidationError("import preview has expired", code="IMPORT_EXPIRED")
        valid = [r for r in preview.rows if r.error_code is None]
        if not valid:
            raise ValidationError('名册没有可导入的有效行，请检查预览中的错误并修改 CSV。', code='NO_VALID_IMPORT_ROWS')
        account_adapter = adapter or self.adapter
        if account_adapter is None:
            raise ValidationError("a native account adapter is required to commit an import")
        now_text = iso(self.service.now())
        with self.service.db.transaction() as db:
            db.execute("UPDATE account_imports SET status='committing',updated_at=? WHERE id=? AND teacher_id=? AND status IN ('preview','committing')", (now_text, batch_id, teacher_id))
        results = []
        for row in valid:
            prior = self.service.db.query_one("SELECT * FROM import_rows WHERE batch_id=? AND row_number=?", (batch_id, row.row_number))
            if prior and prior["status"] == "completed" and prior["user_id"]:
                results.append({"row_number": row.row_number, "status": "completed", "user_id": prior["user_id"]})
                continue
            created_user_id = None
            native_create_started = False
            try:
                if prior and prior["status"] == "provisioning" and prior["user_id"]:
                    user_id = prior["user_id"]
                else:
                    # Mark before the native call. A crash after native create
                    # can then be resolved by exact login on resubmitted CSV.
                    recovering = prior and prior["status"] == "creating"
                    if not recovering and account_adapter.find_user(row.email):
                        raise ConflictError("email already exists", code="ACCOUNT_EXISTS")
                    with self.service.db.transaction() as db:
                        db.execute("UPDATE import_rows SET status='creating' WHERE batch_id=? AND row_number=?", (batch_id, row.row_number))
                    native_create_started = True
                    user_id = account_adapter.find_user(row.email) if recovering else None
                    user_id = user_id or account_adapter.create_user(name=row.name, email=row.email, password=row.password, role="user")
                    created_user_id = user_id
                    # Persist the native ID before enrolling in the classroom
                    # DB; a retry can inspect this provisioning row instead
                    # of silently creating a second account after a crash.
                    with self.service.db.transaction() as db:
                        db.execute("UPDATE import_rows SET status='provisioning',user_id=?,error_code=NULL WHERE batch_id=? AND row_number=?", (user_id, batch_id, row.row_number))
                self.service.enroll_student(user_id, row.name, row.email, must_change_password=True)
                with self.service.db.transaction() as db:
                    db.execute("UPDATE import_rows SET status='completed',user_id=?,error_code=NULL WHERE batch_id=? AND row_number=?", (user_id, batch_id, row.row_number))
                results.append({"row_number": row.row_number, "status": "completed", "user_id": user_id})
            except Exception as exc:
                # Preserve uncertain native work for a same-CSV retry. Deleting
                # here can erase an account after enrollment already committed;
                # marking a timed-out create failed loses its recovery marker.
                retry_state = 'provisioning' if created_user_id or (prior and prior['status'] == 'provisioning') else 'creating' if native_create_started else 'failed'
                with self.service.db.transaction() as db:
                    db.execute("UPDATE import_rows SET status=?,error_code=? WHERE batch_id=? AND row_number=?", (retry_state, getattr(exc, "code", type(exc).__name__), batch_id, row.row_number))
                failed = {"row_number": row.row_number, "status": "failed", "error_code": getattr(exc, "code", type(exc).__name__)}
                results.append(failed)
        status = "completed" if all(r["status"] == "completed" for r in results) else "partial"
        with self.service.db.transaction() as db:
            db.execute("UPDATE account_imports SET status=?,summary_json=?,updated_at=? WHERE id=?", (status, json_dumps({"results": results}), iso(self.service.now()), batch_id))
            db.execute("INSERT INTO teacher_actions(id,actor_id,action,target_ids_json,result_json,created_at) VALUES(?,?,?,?,?,?)", (uuid.uuid4().hex, teacher_id, "account_import", json_dumps([]), json_dumps({"batch_id": batch_id, "status": status}), iso(self.service.now())))
        # Password strings only lived in the preview object; remove it after
        # commit so a long-running teacher process cannot retain them.
        self._forget_preview(batch_id)
        return {"batch_id": batch_id, "status": status, "results": results}

    def reset_password(self, teacher_id: str, user_id: str, new_password: str, *, adapter=None) -> dict:
        if not isinstance(new_password, str) or len(new_password) < 8:
            raise ValidationError("temporary password must contain at least eight characters")
        student = self.service.db.query_one("SELECT * FROM students WHERE user_id=?", (user_id,))
        if not student:
            raise ValidationError("student is not enrolled")
        account_adapter = adapter or self.adapter
        if account_adapter is None:
            raise ValidationError("native account adapter is required")
        self._credential_operation(account_adapter, user_id, teacher_id, True,
                                   lambda: account_adapter.reset_password(user_id=user_id, password=new_password))
        now_text = iso(self.service.now())
        with self.service.db.transaction() as db:
            db.execute("INSERT INTO teacher_actions(id,actor_id,action,target_ids_json,result_json,created_at) VALUES(?,?,?,?,?,?)", (uuid.uuid4().hex, teacher_id, "password_reset", json_dumps([user_id]), json_dumps({"must_change": True}), now_text))
        return {"user_id": user_id, "must_change_password": True, "sessions_revoked": True}

    def change_initial_password(self, user_id: str, current_password: str, new_password: str, *, adapter=None) -> dict:
        if not isinstance(new_password, str) or len(new_password) < 8 or new_password == current_password:
            raise ValidationError("new password does not meet the classroom policy")
        account_adapter = adapter or self.adapter
        if not hasattr(account_adapter, "change_password"):
            raise RuntimeError("native account adapter does not expose the supported password-change operation")
        self._credential_operation(account_adapter, user_id, user_id, False,
                                   lambda: account_adapter.change_password(user_id=user_id, current_password=current_password, new_password=new_password))
        return {"user_id": user_id, "must_change_password": False, "sessions_revoked": True}

    def _credential_operation(self, adapter, user_id, actor_id, must_change, operation):
        # Native HTTP hooks must start revocation after native authentication;
        # revoking before that HTTP call would invalidate its own credential.
        if getattr(adapter, "manages_security", False):
            prior = self.service.db.query_one("SELECT auth_epoch FROM security_states WHERE user_id=?", (user_id,))
            operation()
            state = self.service.db.query_one("SELECT * FROM security_states WHERE user_id=?", (user_id,))
            if not prior or not state or state["auth_epoch"] <= prior[0] or state["credential_operation_state"] != "ready" or bool(state["must_change_password"]) != must_change:
                raise ValidationError("native password operation was not confirmed", code="NATIVE_SECURITY_UNCONFIRMED")
            return
        epoch = self.service.sessions.begin_security_operation(user_id, actor_id=actor_id)
        try:
            operation()
        except Exception:
            self.service.sessions.finish_security_operation(user_id, epoch, success=False, must_change=True, actor_id=actor_id)
            raise
        self.service.sessions.finish_security_operation(user_id, epoch, success=True, must_change=must_change, actor_id=actor_id)
