"""Bounded JSON and signed internal service boundary."""
import json
import time

from .errors import ClassroomError, AuthenticationError, ValidationError


class InternalBoundary:
    def __init__(self, app, authenticator, max_body=16 * 1024 * 1024):
        self.app, self.authenticator, self.max_body = app, authenticator, max_body

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        if path == "/health" and scope["method"] == "GET":
            return await self.app(scope, receive, send)
        try:
            body = bytearray()
            while True:
                event = await receive()
                if event["type"] == "http.disconnect":
                    return
                body.extend(event.get("body", b""))
                if len(body) > self.max_body:
                    raise ValidationError("request body is too large", status=413)
                if not event.get("more_body"):
                    break
            headers = {k.decode().lower(): v.decode("latin1") for k, v in scope["headers"]}
            signature_path = path + ("?" + scope["query_string"].decode("ascii") if scope.get("query_string") else "")
            principal = None
            if self.authenticator is not None:
                identity = self.authenticator.verify(scope["method"], signature_path, bytes(body), headers, now=time.time())
                principal = json.loads(identity)
                if not isinstance(principal, dict) or principal.get("role") not in {"bridge", "admin", "user", "guest"}:
                    raise AuthenticationError("invalid bridge principal")
            if body:
                if headers.get("content-type", "").split(";")[0] != "application/json":
                    raise ValidationError("application/json is required")
                value = json.loads(body)
                if not isinstance(value, dict):
                    raise ValidationError("JSON object is required")
            if principal:
                scope.setdefault("state", {})["bridge_principal"] = principal
            sent = False
            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()
            return await self.app(scope, replay, send)
        except (ValueError, UnicodeError):
            error = ValidationError("invalid JSON request")
        except ClassroomError as exc:
            error = exc
        raw = json.dumps(error.as_dict(), ensure_ascii=False).encode()
        await send({"type": "http.response.start", "status": error.status,
                    "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": raw})
