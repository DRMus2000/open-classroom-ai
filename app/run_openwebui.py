"""Exact-version Open WebUI launcher hook.

The portable distribution invokes this wrapper after the classroom service is
ready.  It intentionally does not use ``open-webui serve`` from an installed
console script because those generated launchers can retain a build-machine
absolute path.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from urllib.request import urlopen


def main() -> int:  # pragma: no cover - called in Windows package
    parser = argparse.ArgumentParser()
    default_data_dir = os.environ.get("DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "openwebui"))
    default_classroom_data = os.environ.get("CLASSROOM_DATA", str(Path(default_data_dir).resolve().parent / "classroom"))
    parser.add_argument("--data-dir", default=default_data_dir)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--classroom-db", default=os.environ.get("CLASSROOM_DB", str(Path(default_classroom_data) / "classroom.db")))
    parser.add_argument("--classroom-data", default=default_classroom_data)
    parser.add_argument("--classroom-health-url", default="http://127.0.0.1:8790/health")
    args = parser.parse_args()
    # Startup integration is checked before exposing any LAN listener.  The
    # exact tested Open WebUI app is wrapped before uvicorn starts; no generated
    # open-webui.exe launcher is used.
    try:
        import json
        with urlopen(args.classroom_health_url, timeout=5) as response:
            health = json.loads(response.read().decode("utf-8"))
        if not health.get("ready"):
            raise RuntimeError("classroom gateway is not ready")
    except Exception as exc:
        print(f"CLASSROOM_NOT_READY: {exc}", file=sys.stderr)
        return 78
    from importlib.metadata import version
    from prepare_installation import schema_hash
    baseline_file = Path(args.data_dir) / 'classroom-baseline.json'
    if version('open-webui') != '0.11.2' or not baseline_file.is_file():
        print("CLASSROOM_NOT_READY: prepare an isolated verified installation before starting", file=sys.stderr)
        return 78
    baseline = json.loads(baseline_file.read_text(encoding='utf-8'))
    if baseline.get('open_webui') != '0.11.2' or baseline.get('schema_sha256') != schema_hash(Path(args.data_dir) / 'webui.db'):
        print("CLASSROOM_NOT_READY: native database no longer matches the verified schema", file=sys.stderr)
        return 78
    # The exact 0.11.2 runtime has a known import-time Alembic cycle.  We only
    # use its supported create/read path after an explicit offline baseline
    # verification; the launcher never silently stamps a live database.
    os.environ.setdefault("ENABLE_DB_MIGRATIONS", "false")
    os.environ.setdefault("FROM_INIT_PY", "true")
    env = os.environ.copy()
    env["DATA_DIR"] = str(Path(args.data_dir).resolve())
    os.environ.update(env)
    # The direct ASGI launcher must provide the same persistent signing secret
    # normally created by the native console launcher.
    if not os.environ.get("WEBUI_SECRET_KEY"):
        import secrets
        secret_file = Path(args.data_dir) / ".webui_secret_key"
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        if not secret_file.exists():
            legacy_secret = Path(__file__).resolve().parents[1] / ".webui_secret_key"
            value = legacy_secret.read_text(encoding="utf-8").strip() if legacy_secret.is_file() else secrets.token_urlsafe(48)
            with secret_file.open("x", encoding="utf-8") as handle:
                handle.write(value)
        secret = secret_file.read_text(encoding="utf-8").strip()
        if len(secret) < 32:
            raise RuntimeError("native signing secret is missing or invalid")
        os.environ["WEBUI_SECRET_KEY"] = secret
    from classroom_service.runtime import InstanceLock
    native_lock = InstanceLock(Path(args.data_dir) / "webui.lock").acquire()
    import atexit
    atexit.register(native_lock.close)
    import open_webui.main
    from openwebui_bridge.middleware import ClassroomRouteGuardMiddleware
    from openwebui_bridge.native_routes import install_native_routes
    from openwebui_bridge.client import BridgeClient
    from openwebui_bridge.auth_hooks import install_auth_hooks
    from openwebui_bridge.file_hook import install_file_hook
    from openwebui_bridge.policy import install_policy_hook
    from urllib.parse import urlsplit
    client = BridgeClient.from_config(args.classroom_data, port=urlsplit(args.classroom_health_url).port or 8790)
    app = open_webui.main.app
    install_policy_hook(open_webui.main)
    install_native_routes(app, client, web_root=Path(__file__).resolve().parents[1] / "web")
    install_auth_hooks(app, client)
    install_file_hook(app, client)
    app.add_middleware(ClassroomRouteGuardMiddleware, client=client, require_bootstrap=True)
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, forwarded_allow_ips="", loop="none", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
