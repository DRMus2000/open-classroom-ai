"""Optional FastAPI adapter around :class:`ClassroomService`.

The state machine remains usable without FastAPI for migration and tests.  In
the portable bundle this module is loaded by the same-origin Open WebUI bridge;
the internal worker API is never exposed to student browsers.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import asyncio
from pathlib import Path
from typing import Any

from .errors import AuthenticationError, ClassroomError, ForbiddenError, NotReadyError, ValidationError
from .service import ClassroomService


class InternalAuthenticator:
    """HMAC verifier for bridge-to-service requests.

    The nonce and timestamp are included in the signed message.  A nonce is
    accepted once and is kept in a bounded in-memory set for the process; the
    bridge and service are single-instance on the teacher computer.
    """
    def __init__(self, secret: bytes | None = None, *, window_seconds: int = 60):
        self.secret = secret or secrets.token_bytes(32)
        self.window_seconds = window_seconds
        self._seen: dict[str, float] = {}

    def sign(self, method: str, path: str, body: bytes, *, timestamp: int, nonce: str, principal: str) -> str:
        message = "\n".join([method.upper(), path, hashlib.sha256(body).hexdigest(), str(timestamp), nonce, principal]).encode()
        return hmac.new(self.secret, message, hashlib.sha256).hexdigest()

    def verify(self, method: str, path: str, body: bytes, headers: dict[str, str], *, now: float) -> str:
        try:
            timestamp = int(headers.get("x-classroom-timestamp", "0"))
            nonce = headers["x-classroom-nonce"]
            principal = headers["x-classroom-principal"]
            supplied = headers["x-classroom-signature"]
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("invalid internal request signature") from exc
        if abs(now - timestamp) > self.window_seconds or not nonce or nonce in self._seen:
            raise AuthenticationError("internal request timestamp or nonce is invalid")
        expected = self.sign(method, path, body, timestamp=timestamp, nonce=nonce, principal=principal)
        if not hmac.compare_digest(supplied, expected):
            raise AuthenticationError("invalid internal request signature")
        self._seen[nonce] = now
        for key, value in list(self._seen.items()):
            if now - value > self.window_seconds:
                self._seen.pop(key, None)
        return principal


def create_app(service: ClassroomService, *, internal_auth: InternalAuthenticator | None = None, accounts=None, exporter=None, web_root=None,
               bridge_only=False, runtime=None, native_url="http://127.0.0.1:3000"):
    try:
        from fastapi import FastAPI, Header, Request, Response, UploadFile, File
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import JSONResponse, FileResponse
    except ImportError as exc:  # pragma: no cover - developer runtime has no FastAPI
        raise RuntimeError("FastAPI is supplied by the portable classroom runtime") from exc

    app = FastAPI(title="Classroom AI gateway", docs_url=None, redoc_url=None)
    if runtime is not None:
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def lifespan(_app):
            await asyncio.to_thread(runtime.start)
            try:
                yield
            finally:
                await asyncio.to_thread(runtime.close)
        app.router.lifespan_context = lifespan
    internal_auth = internal_auth or InternalAuthenticator()
    from .http_boundary import InternalBoundary
    app.add_middleware(InternalBoundary, authenticator=internal_auth if bridge_only else None)
    if web_root:
        root = __import__("pathlib").Path(web_root)
        teacher = root / "teacher"
        student = root / "student"
        guest = root / "guest"
        if teacher.exists():
            app.mount("/classroom/teacher", StaticFiles(directory=teacher, html=True), name="classroom-teacher")
        if student.exists():
            app.mount("/classroom/student", StaticFiles(directory=student, html=True), name="classroom-student")
        if guest.exists():
            app.mount("/classroom/guest", StaticFiles(directory=guest, html=True), name="classroom-guest")

    @app.exception_handler(ClassroomError)
    async def classroom_error_handler(_: Request, exc: ClassroomError):
        return JSONResponse(status_code=exc.status, content=exc.as_dict())

    def token_from_header(value: str | None) -> str:
        if not value:
            raise AuthenticationError("classroom session is required")
        return value[7:] if value.startswith("Bearer ") else value

    def guest_token_from_identity(identity: dict | None) -> str:
        if not isinstance(identity, dict):
            return ""
        token = identity.get("guest_token")
        return token if isinstance(token, str) else ""

    async def principal(request: Request, *, generation: bool = False):
        identity = getattr(request.state, "bridge_principal", None)
        if identity and identity.get("role") == "guest":
            token = guest_token_from_identity(identity)
            if not service.verify_guest_token(token):
                raise AuthenticationError("访客链接已关闭或无效", code="GUEST_LINK_INVALID")
            from .auth import Principal
            return Principal("guest", "guest", "guest", False)
        if identity:
            p = service.sessions.validate_native(identity.get("user_id"), identity.get("token_fingerprint"),
                                                 role=identity.get("role"), require_generation=generation)
            if p.must_change_password and not p.is_teacher and request.url.path not in {
                    "/api/classroom/v1/me", "/api/classroom/v1/account/change-initial-password"}:
                raise ForbiddenError("首次登录必须修改密码", code="PASSWORD_CHANGE_REQUIRED", status=428)
            return p
        if bridge_only:
            raise AuthenticationError("authenticated bridge is required")
        token = token_from_header(request.headers.get("authorization") or request.headers.get("x-classroom-session"))
        return service.sessions.validate(token, require_generation=generation)

    def require_teacher(p):
        if not p.is_teacher:
            raise ForbiddenError("teacher permission is required")

    from .teacher_chat import TeacherChat
    from .guest_chat import GuestChat
    teacher_chat = TeacherChat(service, runtime)
    guest_chat = GuestChat(service, runtime)

    @app.post('/api/classroom/v1/admin/chat/completions')
    async def teacher_completion(request: Request):
        p = await principal(request, generation=True)
        require_teacher(p)
        return teacher_chat.response(p.user_id, await request.json())

    @app.post('/api/classroom/v1/guest/chat/completions')
    async def guest_completion(request: Request):
        identity = getattr(request.state, 'bridge_principal', None)
        if not identity or identity.get('role') != 'guest':
            raise AuthenticationError('访客链接令牌无效', code='GUEST_LINK_INVALID')
        await principal(request, generation=True)
        return guest_chat.response(await request.json())

    @app.get('/api/classroom/v1/guest/status')
    async def guest_status(request: Request):
        identity = getattr(request.state, 'bridge_principal', None)
        if not identity or identity.get('role') != 'guest':
            raise AuthenticationError('访客链接令牌无效', code='GUEST_LINK_INVALID')
        await principal(request)
        models = sorted(service.allowed_models)
        return {
            'ok': True,
            'classroom_paused': service.ready_report()['classroom_paused'],
            'allowed_models': models,
            'model': models[0] if models else None,
        }

    @app.get('/api/classroom/v1/admin/guest-access')
    async def get_guest_access(request: Request):
        p = await principal(request); require_teacher(p)
        return service.get_guest_access()

    @app.put('/api/classroom/v1/admin/guest-access')
    async def update_guest_access(request: Request):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        return service.set_guest_access(
            p.user_id,
            enabled=bool(body.get('enabled')),
            expected_version=body.get('expected_version'),
            rotate=bool(body.get('rotate')),
        )

    @app.get("/api/classroom/v1/readiness")
    async def readiness():
        return service.ready_report()

    @app.get("/api/classroom/v1/me")
    async def me(request: Request):
        p = await principal(request)
        student = service.db.query_one("SELECT * FROM students WHERE user_id=?", (p.user_id,))
        quota = service.quota.read(p.user_id) if student else None
        active = service.db.query_one("SELECT id,status,version,chat_id,assistant_message_id FROM review_requests WHERE user_id=? AND status IN ('pending','approved_queued','generating') ORDER BY submitted_at DESC,id DESC LIMIT 1", (p.user_id,))
        latest = service.db.query_one("SELECT id,status,version,chat_id,assistant_message_id FROM review_requests WHERE user_id=? ORDER BY submitted_at DESC,id DESC LIMIT 1", (p.user_id,))
        return {"user": {"id": p.user_id, "roster_name": student["roster_name"] if student else None, "login": student["login_identifier"] if student else None}, "must_change_password": p.must_change_password, "classroom_paused": service.ready_report()["classroom_paused"], "allowed_models": sorted(service.allowed_models), "quota": quota, "active_request": dict(active) if active else None, "latest_request": dict(latest) if latest else None, "review_mode": service.get_review_mode()["mode"]}

    @app.post("/api/classroom/v1/requests")
    async def submit(request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        p = await principal(request, generation=True)
        body = await request.json()
        if not isinstance(body, dict):
            raise ValidationError("request body must be an object")
        operation_id = idempotency_key or body.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValidationError("Idempotency-Key is required")
        payload = body.get("payload")
        if "user_id" in body or "role" in body or "approved" in body:
            raise ValidationError("identity and approval fields are server controlled")
        parent_message = body.get("parent_message_id")
        if parent_message:
            parent = service.db.query_one("SELECT id FROM review_requests WHERE user_id=? AND chat_id=? AND assistant_message_id=? ORDER BY submitted_at DESC LIMIT 1", (p.user_id, body.get("chat_id"), parent_message))
            if not parent:
                raise ValidationError("parent answer is not in the classroom archive")
            body["parent_request_id"] = parent[0]
        return service.submit(p.user_id, operation_id, payload, chat_id=body.get("chat_id"), user_message_id=body.get("user_message_id"), assistant_message_id=body.get("assistant_message_id"), parent_request_id=body.get("parent_request_id"), attachment_ids=body.get("attachment_ids"))

    @app.get("/api/classroom/v1/requests")
    async def mine(request: Request, status: str | None = None, limit: int = 50, cursor: str | None = None):
        p = await principal(request)
        return {"requests": service.list_requests(status=status, user_id=p.user_id, limit=limit, cursor=cursor)}

    @app.post("/api/classroom/v1/requests/{request_id}/delivery")
    async def delivery(request: Request, request_id: str):
        p = await principal(request)
        body = await request.json()
        service.record_delivery(request_id, p.user_id, body.get("seq"), consumer_id=p.session_fingerprint)
        return {"acknowledged": True}

    @app.get("/api/classroom/v1/requests/{request_id}")
    async def get_request(request: Request, request_id: str):
        p = await principal(request)
        return service.get_request(request_id, user_id=p.user_id)

    @app.get("/api/classroom/v1/requests/{request_id}/events")
    async def events(request: Request, request_id: str, after_seq: int = 0):
        p = await principal(request)
        return {"events": service.events(request_id, after_seq=after_seq, user_id=p.user_id)}

    @app.post("/api/classroom/v1/requests/{request_id}/cancel")
    async def cancel(request: Request, request_id: str):
        p = await principal(request)
        return service.cancel(request_id, p.user_id, source="student")

    @app.post("/api/classroom/v1/attachments")
    async def upload(request: Request):
        p = await principal(request, generation=True)
        body = await request.json()
        if not isinstance(body, dict) or not isinstance(body.get("filename"), str) or not isinstance(body.get("content_base64"), str):
            raise ValidationError("filename and content_base64 are required")
        try:
            content = base64.b64decode(body["content_base64"], validate=True)
        except Exception as exc:
            raise ValidationError("invalid base64 attachment") from exc
        return service.attachments.add(p.user_id, body["filename"], content, media_type=body.get("media_type"), encoding=body.get("encoding"))

    @app.get("/api/classroom/v1/attachments/{attachment_id}/content")
    async def attachment_content(request: Request, attachment_id: str, download: bool = False):
        p = await principal(request)
        item = service.attachments.get(attachment_id, user_id=None if p.is_teacher else p.user_id)
        from urllib.parse import quote
        return Response(item["content"], media_type=item["media_type"], headers={
            "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Content-Disposition": ("attachment" if download else "inline") + "; filename*=UTF-8''" + quote(item["original_filename"])})

    def native_adapter(request):
        from .accounts import OpenWebUIHTTPAccountAdapter
        identity = getattr(request.state, "bridge_principal", {})
        token = identity.get("native_token", "")
        if not token or hashlib.sha256(token.encode()).hexdigest() != identity.get("token_fingerprint"):
            raise AuthenticationError("a request-scoped native credential is required")
        return OpenWebUIHTTPAccountAdapter(native_url, token)

    @app.post("/api/classroom/v1/account/change-initial-password")
    async def change_initial_password(request: Request):
        p = await principal(request)
        if accounts is None:
            raise NotReadyError("native account password adapter is not configured")
        body = await request.json()
        return await asyncio.to_thread(accounts.change_initial_password, p.user_id, body.get("current_password"), body.get("new_password"),
                                       adapter=native_adapter(request) if bridge_only else None)

    @app.get("/api/classroom/v1/admin/requests")
    async def admin_requests(request: Request, status: str | None = None, user_id: str | None = None, limit: int = 50, cursor: str | None = None):
        p = await principal(request); require_teacher(p)
        return {"requests": service.list_requests(status=status, user_id=user_id, limit=limit, cursor=cursor)}

    @app.get("/api/classroom/v1/admin/students")
    async def admin_students(request: Request):
        p = await principal(request); require_teacher(p)
        return {"students": service.list_students()}

    @app.post("/api/classroom/v1/admin/accounts/import/preview")
    @app.post("/api/classroom/v1/admin/imports/preview")
    async def import_preview(request: Request):
        p = await principal(request); require_teacher(p)
        if accounts is None:
            raise NotReadyError("account provisioner is unavailable")
        body = await request.json()
        return accounts.preview(p.user_id, body.get("csv", body.get("content")))

    @app.post("/api/classroom/v1/admin/accounts/import/{batch_id}/commit")
    @app.post("/api/classroom/v1/admin/imports/{batch_id}/commit")
    async def import_commit(request: Request, batch_id: str):
        p = await principal(request); require_teacher(p)
        if accounts is None:
            raise NotReadyError("account provisioner is unavailable")
        return await asyncio.to_thread(accounts.commit, p.user_id, batch_id, adapter=native_adapter(request) if bridge_only else None)

    @app.post("/api/classroom/v1/admin/students/{student_id}/reset-password")
    async def reset_password(request: Request, student_id: str):
        p = await principal(request); require_teacher(p)
        if accounts is None:
            raise NotReadyError("account provisioner is unavailable")
        body = await request.json()
        return await asyncio.to_thread(accounts.reset_password, p.user_id, student_id, body.get("new_password", body.get("password")), adapter=native_adapter(request) if bridge_only else None)

    @app.patch("/api/classroom/v1/admin/students/{student_id}")
    async def edit_student(request: Request, student_id: str):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        return service.set_student_state(p.user_id, student_id, ai_enabled=body.get("ai_enabled"), roster_name=body.get("roster_name"))

    @app.post("/api/classroom/v1/admin/requests/{request_id}/stop")
    async def stop(request: Request, request_id: str):
        p = await principal(request); require_teacher(p)
        return service.cancel(request_id, service.get_request(request_id)["user_id"], source="teacher")

    @app.post("/api/classroom/v1/admin/requests/bulk-decision")
    async def bulk_decision(request: Request):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        rows = body.get("requests")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 30 or body.get("decision") not in {"approve", "reject"}:
            raise ValidationError("select one to thirty requests to approve or reject")
        results = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValidationError("invalid decision row")
            try:
                result = service.decide(row.get("id"), p.user_id, body["decision"], expected_version=row.get("version"), note=body.get("note", ""))
                results.append({"id": row["id"], "result": result})
            except ClassroomError as exc:
                results.append({"id": row.get("id"), **exc.as_dict()})
        return {"results": results}

    @app.post("/api/classroom/v1/admin/requests/{request_id}/decision")
    async def decision(request: Request, request_id: str):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        return service.decide(request_id, p.user_id, body.get("decision"), expected_version=body.get("expected_version"), note=body.get("note", ""), edited_payload=body.get("edited_payload"), attachment_ids=body.get("attachment_ids"))

    @app.post("/api/classroom/v1/admin/quotas/adjust")
    async def quota_adjust(request: Request):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        key = request.headers.get("idempotency-key")
        if not key or not isinstance(body.get("expected_versions"), dict) or not body.get("date"):
            raise ValidationError("Idempotency-Key, date and expected_versions are required")
        return service.quota.adjust_many(body.get("user_ids", []), delta=body.get("delta"), actor_id=p.user_id, reason=body.get("reason", "课堂临时调整"), expected_versions=body["expected_versions"], operation_key=key, requested_date=body["date"], require_versions=True)

    @app.post("/api/classroom/v1/admin/quotas/preview")
    async def quota_preview(request: Request):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        if body.get("date") and body["date"] != service.quota.day_info()[0]:
            raise ValidationError("额度日期已变化，请重新预览", status=409)
        return service.quota_preview(body.get("user_ids", []), body.get("delta"))

    @app.put("/api/classroom/v1/admin/classroom/state")
    async def classroom_state(request: Request):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        return service.set_classroom_paused(p.user_id, body.get("paused"), body.get("reason", ""))

    @app.put("/api/classroom/v1/admin/model-policy")
    async def model_policy(request: Request):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        return service.set_allowed_models(p.user_id, body.get("allowed_models", []))

    @app.get('/api/classroom/v1/admin/system-prompt')
    async def get_system_prompt(request: Request):
        p = await principal(request); require_teacher(p)
        return service.get_system_prompt()

    @app.put('/api/classroom/v1/admin/system-prompt')
    async def update_system_prompt(request: Request):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        return service.set_system_prompt(p.user_id, body.get('prompt'), body.get('expected_version'))

    @app.get('/api/classroom/v1/admin/review-mode')
    async def get_review_mode(request: Request):
        p = await principal(request); require_teacher(p)
        return service.get_review_mode()

    @app.put('/api/classroom/v1/admin/review-mode')
    async def update_review_mode(request: Request):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        return service.set_review_mode(p.user_id, body.get('mode'), body.get('expected_version'))

    @app.get('/api/classroom/v1/admin/audit-system-prompt')
    async def get_audit_system_prompt(request: Request):
        p = await principal(request); require_teacher(p)
        return service.get_audit_system_prompt()

    @app.put('/api/classroom/v1/admin/audit-system-prompt')
    async def update_audit_system_prompt(request: Request):
        p = await principal(request); require_teacher(p)
        body = await request.json()
        return service.set_audit_system_prompt(p.user_id, body.get('prompt'), body.get('expected_version'))

    @app.get('/api/classroom/v1/admin/ai-audit/history')
    async def ai_audit_history(request: Request, limit: int = 50, cursor: str | None = None):
        p = await principal(request); require_teacher(p)
        return service.list_ai_audit_history(limit=limit, cursor=cursor)

    @app.post('/api/classroom/v1/admin/ai-audit/clear-session')
    async def clear_ai_audit_session(request: Request):
        p = await principal(request); require_teacher(p)
        return service.clear_ai_audit_session(p.user_id)

    @app.get('/api/classroom/v1/admin/insights')
    async def admin_insights(request: Request, range: str = 'today'):
        p = await principal(request); require_teacher(p)
        return service.classroom_insights(range_name=range)

    @app.get("/api/classroom/v1/admin/health")
    async def admin_health(request: Request):
        p = await principal(request); require_teacher(p)
        return service.ready_report()

    @app.get("/api/classroom/v1/admin/audit")
    async def audit(request: Request, limit: int = 100):
        p = await principal(request); require_teacher(p)
        return {"audit": service.audit(limit=limit)}

    @app.post("/api/classroom/v1/admin/exports")
    async def export_data(request: Request):
        p = await principal(request); require_teacher(p)
        if exporter is None:
            raise NotReadyError("exporter is not configured")
        body = await request.json()
        path = exporter.export(p.user_id, user_ids=body.get("user_ids"), include_attachments=bool(body.get("include_attachments", True)))
        return {"download": "/api/classroom/v1/admin/exports/" + path.name, "filename": path.name}

    @app.get("/api/classroom/v1/admin/exports/{filename}")
    async def download_export(request: Request, filename: str):
        p = await principal(request); require_teacher(p)
        if exporter is None or Path(filename).name != filename or not filename.endswith(".zip"):
            raise ValidationError("invalid export", status=404)
        path = (exporter.output_root / filename).resolve()
        if path.parent != exporter.output_root.resolve() or not path.is_file():
            raise ValidationError("export not found", status=404)
        return FileResponse(path, filename=filename, media_type="application/zip", headers={"Cache-Control": "no-store"})

    @app.get("/internal/v1/readiness")
    async def internal_readiness(request: Request):
        if not bridge_only:
            body = await request.body()
            internal_auth.verify("GET", "/internal/v1/readiness", body, dict(request.headers), now=__import__("time").time())
        return service.ready_report()

    @app.post("/internal/v1/drain")
    async def drain(request: Request):
        if not bridge_only or getattr(request.state, 'bridge_principal', {}).get('role') != 'bridge' or runtime is None:
            raise AuthenticationError('signed runtime maintenance is required')
        await asyncio.to_thread(runtime.close)
        return {'drained': True}

    @app.post("/internal/v1/guest/validate")
    async def guest_validate(request: Request):
        identity = getattr(request.state, "bridge_principal", {})
        if not bridge_only or identity.get("role") != "bridge":
            raise AuthenticationError("signed bridge control is required")
        body = await request.json()
        if not service.verify_guest_token(body.get("token", "")):
            raise AuthenticationError("访客链接已关闭或无效", code="GUEST_LINK_INVALID")
        return {"ok": True}

    @app.post("/internal/v1/identity/{operation}")
    async def identity_control(request: Request, operation: str):
        identity = getattr(request.state, "bridge_principal", {})
        if not bridge_only or identity.get("role") != "bridge":
            raise AuthenticationError("signed bridge control is required")
        body = await request.json()
        uid = body.get("user_id")
        if not isinstance(uid, str) or not uid or len(uid) > 200:
            raise ValidationError("valid user_id is required")
        if operation == "prepare":
            if body.get("role") == "admin":
                from .clock import iso
                with service.db.transaction() as db:
                    db.execute("INSERT OR IGNORE INTO security_states(user_id,must_change_password,auth_epoch,credential_operation_state,updated_at) VALUES(?,0,0,'ready',?)", (uid, iso(service.now())))
            elif body.get("role") == "user":
                student = service.db.query_one("SELECT * FROM students WHERE user_id=?", (uid,))
                if not student or student["enrollment_state"] != "active":
                    raise ForbiddenError("学生不在有效课堂名册中")
            else:
                raise ForbiddenError("native role is not active")
            state = service.db.query_one("SELECT auth_epoch FROM security_states WHERE user_id=?", (uid,))
            if not state:
                raise AuthenticationError("security state is not initialized")
            return {"epoch": state[0]}
        if operation == "issued":
            service.sessions.session_issued(uid, body.get("token_fingerprint", ""), native_expires_at=body["expires_at"], expected_epoch=body["epoch"])
        elif operation == "validate":
            p = service.sessions.validate_native(uid, body.get("token_fingerprint", ""), role=body.get("role"), require_generation=bool(body.get("generation")))
            return {"user_id": p.user_id, "role": p.role, "must_change_password": p.must_change_password}
        elif operation == "begin":
            return {"epoch": service.sessions.begin_security_operation(uid, actor_id=body["actor_id"])}
        elif operation == "finish":
            if type(body.get("success")) is not bool or type(body.get("must_change")) is not bool:
                raise ValidationError("security results must be booleans")
            service.sessions.finish_security_operation(uid, body["epoch"], success=body["success"], must_change=body["must_change"], actor_id=body["actor_id"])
        elif operation == "revoke":
            service.sessions.revoke_user(uid, actor_id=uid)
        elif operation == "file-linked":
            item = service.attachments.get(body["attachment_id"], user_id=uid)
            with service.db.transaction() as db:
                db.execute("INSERT INTO native_attachments(user_id,native_file_id,attachment_id) VALUES(?,?,?)", (uid, body["native_file_id"], item["id"]))
        elif operation == "files-resolve":
            ids = body.get("native_file_ids", [])
            op = body.get("operation_id")
            if not isinstance(op, str) or not 1 <= len(op) <= 200:
                raise ValidationError("operation_id is required")
            if not isinstance(ids, list) or len(ids) > 5 or any(not isinstance(i, str) for i in ids):
                raise ValidationError("invalid native attachment list")
            items = []
            for fid in ids:
                copy = service.db.query_one("SELECT attachment_id FROM native_attachment_copies WHERE user_id=? AND operation_id=? AND native_file_id=?", (uid, op, fid))
                if copy:
                    item = service.attachments.get(copy[0], user_id=uid)
                    items.append({"id": item["id"], "sha256": item["sha256"]})
                    continue
                row = service.db.query_one("SELECT attachment_id FROM native_attachments WHERE user_id=? AND native_file_id=?", (uid, fid))
                if not row:
                    raise ForbiddenError("native file has not been copied to the classroom archive")
                item = service.attachments.get(row[0], user_id=uid)
                # Reusing a native file in another request receives its own
                # immutable attachment row; earlier snapshots remain intact.
                if item["request_id"]:
                    item = service.attachments.add(uid, item["original_filename"], item["content"], encoding=item["text_encoding"])
                with service.db.transaction() as db:
                    db.execute("INSERT OR IGNORE INTO native_attachment_copies(user_id,operation_id,native_file_id,attachment_id) VALUES(?,?,?,?)", (uid, op, fid, item["id"]))
                    winner = db.execute("SELECT attachment_id FROM native_attachment_copies WHERE user_id=? AND operation_id=? AND native_file_id=?", (uid, op, fid)).fetchone()
                item = service.attachments.get(winner[0], user_id=uid)
                items.append({"id": item["id"], "sha256": item["sha256"]})
            return {"attachments": items}
        elif operation == "cancel-chat":
            rows = service.db.query_all("SELECT id FROM review_requests WHERE user_id=? AND chat_id=? AND status IN ('pending','approved_queued','generating')", (uid, body.get("chat_id")))
            for row in rows:
                service.cancel(row[0], uid, source="student")
        else:
            raise ValidationError("unknown identity operation", status=404)
        return {"ok": True}

    @app.get("/health")
    async def health():
        report = service.ready_report()
        return {"ready": bool(report.get("ready"))}

    return app


def main() -> None:  # pragma: no cover - invoked in the portable runtime
    import argparse
    parser = argparse.ArgumentParser(description="Classroom AI gateway")
    parser.add_argument("--db", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--native-url", default="http://127.0.0.1:3000")
    args = parser.parse_args()
    from .database import ClassroomDB
    from .service import ClassroomService
    from .archive import ClassroomExporter
    import uvicorn
    from .runtime import InstanceLock, ClassroomRuntime
    from .worker import HttpUpstream
    from .accounts import AccountProvisioner
    if args.host not in {"127.0.0.1", "::1"}:
        parser.error("internal service must bind to loopback")
    endpoint = os.environ.get("CLASSROOM_PROVIDER_URL", "")
    api_key = os.environ.get("CLASSROOM_PROVIDER_API_KEY", "")
    if not endpoint or not api_key:
        parser.error("CLASSROOM_PROVIDER_URL and CLASSROOM_PROVIDER_API_KEY are required")
    lock = InstanceLock(Path(args.data_root) / "service.lock").acquire()
    db = None
    try:
        key_file = Path(args.data_root) / "bridge.key"
        if not key_file.exists():
            with key_file.open("xb") as handle:
                handle.write(secrets.token_bytes(32))
        secret = key_file.read_bytes()
        if len(secret) != 32:
            raise RuntimeError("invalid installation bridge key")
        db = ClassroomDB(args.db)
        models = {m.strip() for m in os.environ["CLASSROOM_MODELS"].split(",") if m.strip()} if "CLASSROOM_MODELS" in os.environ else None
        service = ClassroomService(db, data_root=args.data_root, allowed_models=models,
                                   timezone_name=os.environ.get("CLASSROOM_TIMEZONE") or None)
        service.configure_provider(hmac.new(secret, (endpoint.rstrip('/') + '\n' + api_key).encode(), hashlib.sha256).hexdigest())
        runtime = ClassroomRuntime(service, HttpUpstream(endpoint, lambda: api_key))
        app = create_app(service, internal_auth=InternalAuthenticator(secret), accounts=AccountProvisioner(service),
                         exporter=ClassroomExporter(service, Path(args.data_root) / "exports"),
                         bridge_only=True, runtime=runtime, native_url=args.native_url)
        uvicorn.run(app, host=args.host, port=args.port, workers=1, access_log=False)
    finally:
        if db:
            db.close()
        lock.close()


if __name__ == "__main__":
    main()
