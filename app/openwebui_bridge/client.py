"""Authenticated transport; the WebUI process owns no classroom database/key."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import secrets
import time

try:
    from classroom_service.api import InternalAuthenticator
except ImportError:
    from ..classroom_service.api import InternalAuthenticator


class BridgeClient:
    def __init__(self, base_url: str, secret: bytes):
        from urllib.parse import urlsplit
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}:
            raise ValueError("internal classroom service must use loopback")
        self.base_url = base_url.rstrip("/")
        self.auth = InternalAuthenticator(secret)
        self._http = None

    def _session(self):
        import httpx
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=60, follow_redirects=False, trust_env=False)
        return self._http

    async def aclose(self):
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @classmethod
    def from_config(cls, data_root, port=8790):
        secret = (Path(data_root) / "bridge.key").read_bytes()
        if len(secret) != 32:
            raise RuntimeError("invalid classroom installation key")
        return cls(f"http://127.0.0.1:{port}", secret)

    def headers(self, method, path, raw, principal):
        timestamp, nonce = int(time.time()), secrets.token_hex(16)
        identity = json.dumps(principal, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return {"Content-Type": "application/json", "X-Classroom-Timestamp": str(timestamp),
                "X-Classroom-Nonce": nonce, "X-Classroom-Principal": identity,
                "X-Classroom-Signature": self.auth.sign(method, path, raw, timestamp=timestamp, nonce=nonce, principal=identity)}

    async def request(self, method, path, *, principal, body=None, raw=None, extra_headers=None):
        import httpx
        raw = (json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode() if body is not None else b"") if raw is None else raw
        headers = self.headers(method, path, raw, principal)
        # Only these non-authority headers may be forwarded by the bridge.
        for key, value in (extra_headers or {}).items():
            if key.lower() in {"idempotency-key"}:
                headers[key] = value
        return await self._session().request(method, self.base_url + path, content=raw, headers=headers)

    async def control(self, operation, body=None):
        from fastapi import HTTPException
        response = await self.request("POST", "/internal/v1/" + operation,
                                      principal={"role": "bridge"}, body=body or {})
        if response.status_code >= 400:
            try:
                detail = response.json().get("error", {}).get("message", "课堂安全服务拒绝请求")
            except ValueError:
                detail = "课堂安全服务不可用"
            raise HTTPException(response.status_code, detail)
        return response.json()

    async def download(self, path, principal, *, method='GET', body=None):
        """Relay exports without buffering an entire class archive in RAM."""
        import httpx
        from fastapi.responses import StreamingResponse
        from starlette.background import BackgroundTask
        session = self._session()
        raw = json.dumps(body, ensure_ascii=False).encode() if body is not None else b''
        response = await session.send(session.build_request(method, self.base_url + path,
            content=raw, headers=self.headers(method, path, raw, principal)), stream=True)
        if response.status_code >= 400:
            from fastapi import HTTPException
            await response.aread()
            await response.aclose()
            try:
                detail = response.json().get('error', {}).get('message', '课堂服务拒绝请求')
            except ValueError:
                detail = '课堂服务拒绝请求'
            raise HTTPException(response.status_code, detail)
        async def close():
            await response.aclose()
        async def chunks():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await close()
        headers = {k: v for k, v in response.headers.items() if k.lower() in {'content-type', 'content-disposition'}}
        headers['Cache-Control'] = 'no-store'
        return StreamingResponse(chunks(), status_code=response.status_code, headers=headers, background=BackgroundTask(close))

    @staticmethod
    def principal(user, token):
        return {"user_id": user.id, "role": user.role,
                "token_fingerprint": hashlib.sha256(token.encode()).hexdigest()}
