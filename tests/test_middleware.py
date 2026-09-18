import asyncio
import json

from classroom.app.openwebui_bridge.middleware import ClassroomRouteGuardMiddleware


def run_asgi(app, path, headers=None, client=("192.0.2.10", 1)):
    messages = []
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        messages.append(message)
    asyncio.run(app({"type": "http", "path": path, "method": "POST", "headers": headers or [], "client": client}, receive, send))
    return messages


def test_openwebui_provider_routes_fail_closed_without_app_call():
    called = []
    async def app(*args):
        called.append(True)
    messages = run_asgi(ClassroomRouteGuardMiddleware(app), "/openai/chat/completions")
    assert not called
    assert messages[0]["status"] == 403
    assert "CLASSROOM_PIPE_REQUIRED" in messages[1]["body"].decode()


def test_auxiliary_model_routes_are_also_closed():
    for path in ("/api/v1/tasks/title", "/api/v1/embeddings", "/api/v1/tools/execute", "/api/v1/search"):
        called = []

        async def app(*args):
            called.append(True)

        messages = run_asgi(ClassroomRouteGuardMiddleware(app), path)
        assert not called
        assert messages[0]["status"] == 403


def test_loopback_bootstrap_marker_cannot_bypass_authentication():
    called = []

    async def app(*args):
        called.append(True)

    messages = run_asgi(ClassroomRouteGuardMiddleware(app), "/api/v1/functions/create", headers=[(b"x-classroom-bootstrap", b"1")], client=("127.0.0.1", 1))
    assert not called
    assert messages[0]['status'] == 403
