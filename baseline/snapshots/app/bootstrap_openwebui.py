"""First-run bootstrap for the offline classroom Open WebUI package."""

from __future__ import annotations

import json
import os
import secrets
import string
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBUI_URL = "http://127.0.0.1:3000"
OPENWEBUI_DATA = Path(os.environ.get("DATA_DIR", str(ROOT / "data" / "openwebui")))
CREDENTIALS = OPENWEBUI_DATA / "teacher-admin.json"
FILTER_FILE = ROOT / "app" / "open_webui_review_filter.py"
FUNCTION_ID = "classroom_review_gate"


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
            data = response.read().decode("utf-8")
            return response.status, json.loads(data) if data else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = {"detail": body[:500]}
        return exc.code, detail
    except (OSError, urllib.error.URLError) as exc:
        return 0, {"detail": str(exc)}


def password() -> str:
    alphabet = string.ascii_letters + string.digits + "-_!"
    return "".join(secrets.choice(alphabet) for _ in range(20))


def wait_ready() -> None:
    for _ in range(180):
        status, _ = request_json("GET", WEBUI_URL + "/health")
        if status == 200:
            return
        time.sleep(1)
    raise RuntimeError("Open WebUI did not become ready within 180 seconds")


def sign_in_or_create() -> tuple[str, dict]:
    OPENWEBUI_DATA.mkdir(parents=True, exist_ok=True)
    if CREDENTIALS.exists():
        saved = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
        status, result = request_json(
            "POST",
            WEBUI_URL + "/api/v1/auths/signin",
            {"email": saved["email"], "password": saved["password"]},
        )
        if status == 200 and isinstance(result, dict) and result.get("token"):
            return result["token"], saved
        raise RuntimeError("Saved teacher credentials were rejected; see data/openwebui/teacher-admin.json")

    credentials = {
        "name": "Teacher",
        "email": "teacher@school.local",
        "password": password(),
    }
    status, result = request_json("POST", WEBUI_URL + "/api/v1/auths/signup", credentials)
    if status not in (200, 201):
        raise RuntimeError(f"Initial teacher signup failed (HTTP {status}): {result}")
    CREDENTIALS.write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding="utf-8")
    status, result = request_json(
        "POST",
        WEBUI_URL + "/api/v1/auths/signin",
        {"email": credentials["email"], "password": credentials["password"]},
    )
    if status != 200 or not isinstance(result, dict) or not result.get("token"):
        raise RuntimeError(f"Teacher signin failed (HTTP {status}): {result}")
    return result["token"], credentials


def install_filter(token: str) -> None:
    content = FILTER_FILE.read_text(encoding="utf-8")
    payload = {
        "id": FUNCTION_ID,
        "name": "Classroom Review Gate",
        "content": content,
        "meta": {
            "description": "Require teacher approval before a student message reaches an AI model.",
            "manifest": {"title": "Classroom Review Gate", "version": "1.1.0"},
        },
    }
    endpoint = WEBUI_URL + "/api/v1/functions/id/" + FUNCTION_ID
    status, _ = request_json("GET", endpoint, token=token)
    if status == 200:
        status, result = request_json("POST", endpoint + "/update", payload, token)
    elif status in (401, 404):
        status, result = request_json("POST", WEBUI_URL + "/api/v1/functions/create", payload, token)
    else:
        raise RuntimeError(f"Could not inspect review filter (HTTP {status})")
    if status < 200 or status >= 300:
        raise RuntimeError(f"Could not install review filter (HTTP {status}): {result}")

    status, state = request_json("GET", endpoint, token=token)
    if status != 200 or not isinstance(state, dict):
        raise RuntimeError("Review filter was installed but could not be read back")
    if not state.get("is_active"):
        status, state = request_json("POST", endpoint + "/toggle", token=token)
        if status < 200 or status >= 300:
            raise RuntimeError(f"Could not activate review filter (HTTP {status})")
    if not state.get("is_global"):
        status, _ = request_json("POST", endpoint + "/toggle/global", token=token)
        if status < 200 or status >= 300:
            raise RuntimeError(f"Could not set review filter global (HTTP {status})")


def main() -> int:
    try:
        wait_ready()
        token, credentials = sign_in_or_create()
        install_filter(token)
        print("BOOTSTRAP_OK")
        print(f"TEACHER_EMAIL={credentials['email']}")
        print(f"TEACHER_PASSWORD={credentials['password']}")
        return 0
    except Exception as exc:
        print(f"BOOTSTRAP_ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
