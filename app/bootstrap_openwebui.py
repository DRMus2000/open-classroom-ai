"""One-time, credential-safe Open WebUI classroom bootstrap.

The administrator credentials are supplied by the launcher environment for this
process.  They are never written to a JSON file or printed.  First-admin
creation is performed by Open WebUI's supported startup environment variables;
this script only signs in and installs the exact-version Pipe.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBUI_URL = os.environ.get("CLASSROOM_OPENWEBUI_URL", "http://127.0.0.1:3000")
PIPE_FILE = Path(__file__).resolve().with_name("openwebui_classroom_pipe.py")
PIPE_ID = "classroom_pipe"
OLD_FILTER_ID = "classroom_review_gate"


def request_json(method: str, url: str, payload: dict | None = None, token: str = ""):
    raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, method=method, data=raw)
    req.add_header("Accept", "application/json")
    if raw is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            value = response.read().decode("utf-8")
            return response.status, json.loads(value) if value else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = {"detail": body[:400]}
        return exc.code, detail
    except OSError as exc:
        return 0, {"detail": str(exc)}


def wait_ready() -> None:
    for _ in range(180):
        status, _ = request_json("GET", WEBUI_URL + "/health")
        if status == 200:
            return
        time.sleep(1)
    raise RuntimeError("Open WebUI did not become ready")


def sign_in() -> str:
    email = os.environ.get("WEBUI_ADMIN_EMAIL", "").strip()
    password = os.environ.get("WEBUI_ADMIN_PASSWORD", "")
    if not email or not password:
        raise RuntimeError("set WEBUI_ADMIN_EMAIL and WEBUI_ADMIN_PASSWORD for this one-time bootstrap; no password file is created")
    status, result = request_json("POST", WEBUI_URL + "/api/v1/auths/signin", {"email": email, "password": password})
    if status != 200 or not isinstance(result, dict) or not result.get("token"):
        raise RuntimeError(f"administrator sign-in failed (HTTP {status})")
    return result["token"]


def install_function(token: str, function_id: str, content: str, name: str, function_type: str) -> dict:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    payload = {"id": function_id, "name": name, "content": content, "meta": {"description": "Classroom AI managed model exit", "manifest": {"title": name, "version": "2.0.0", "type": function_type, "content_sha256": digest}}}
    endpoint = WEBUI_URL + "/api/v1/functions/id/" + function_id
    status, _ = request_json("GET", endpoint, token=token)
    if status == 200:
        status, result = request_json("POST", endpoint + "/update", payload, token=token)
    elif status in (401, 404):
        status, result = request_json("POST", WEBUI_URL + "/api/v1/functions/create", payload, token=token)
    else:
        raise RuntimeError(f"could not inspect function {function_id} (HTTP {status})")
    if status < 200 or status >= 300:
        raise RuntimeError(f"could not install function {function_id} (HTTP {status})")
    status, state = request_json("GET", endpoint, token=token)
    if status != 200 or not isinstance(state, dict):
        raise RuntimeError(f"function {function_id} did not read back")
    state_hash = (((state.get("meta") or {}).get("manifest") or {}).get("content_sha256"))
    if state_hash and state_hash != digest:
        raise RuntimeError(f"function {function_id} content hash mismatch")
    if not state.get("is_active"):
        status, _ = request_json("POST", endpoint + "/toggle", token=token)
        if status < 200 or status >= 300:
            raise RuntimeError(f"could not activate function {function_id}")
    if not state.get("is_global"):
        status, _ = request_json("POST", endpoint + "/toggle/global", token=token)
        if status < 200 or status >= 300:
            raise RuntimeError(f"could not make function {function_id} global")
    return {"id": function_id, "sha256": digest}


def disable_legacy_filter(token: str) -> None:
    endpoint = WEBUI_URL + "/api/v1/functions/id/" + OLD_FILTER_ID
    status, state = request_json("GET", endpoint, token=token)
    if status != 200 or not isinstance(state, dict):
        return
    if state.get("is_active"):
        request_json("POST", endpoint + "/toggle", token=token)
    if state.get("is_global"):
        request_json("POST", endpoint + "/toggle/global", token=token)


def main() -> int:
    try:
        wait_ready()
        token = sign_in()
        pipe = install_function(token, PIPE_ID, PIPE_FILE.read_text(encoding="utf-8"), "Classroom Pipe", "pipe")
        disable_legacy_filter(token)
        status, result = request_json('POST', WEBUI_URL + '/api/classroom/bootstrap-complete', {}, token=token)
        if status != 200 or not result.get('ready'):
            raise RuntimeError('native classroom configuration verification failed')
        print(json.dumps({"status": "BOOTSTRAP_OK", "pipe": pipe, "password_persisted": False}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"BOOTSTRAP_ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
