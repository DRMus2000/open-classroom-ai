import asyncio
from datetime import timedelta
import hashlib
import json
import sys
import types

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.staticfiles import StaticFiles

from classroom.app.classroom_service.api import create_app, InternalAuthenticator
from classroom.app.openwebui_bridge.client import BridgeClient
from classroom.app.openwebui_bridge.middleware import ClassroomRouteGuardMiddleware
from classroom.app.openwebui_bridge.native_routes import install_native_routes


class LocalClient(BridgeClient):
    def __init__(self, app, key):
        super().__init__('http://127.0.0.1:8790', key)
        self.app = app

    async def request(self, method, path, *, principal, body=None, raw=None, extra_headers=None):
        raw = json.dumps(body).encode() if raw is None and body is not None else raw or b''
        headers = self.headers(method, path, raw, principal)
        headers.update({k: v for k, v in (extra_headers or {}).items() if k.lower() == 'idempotency-key'})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=self.base_url) as client:
            return await client.request(method, path, headers=headers, content=raw)


def installation(service):
    key = b'k' * 32
    return LocalClient(create_app(service, internal_auth=InternalAuthenticator(key), bridge_only=True), key)


def issue(service, uid, token):
    epoch = service.db.query_one('SELECT auth_epoch FROM security_states WHERE user_id=?', (uid,))[0]
    service.sessions.session_issued(uid, hashlib.sha256(token.encode()).hexdigest(), native_expires_at=(service.now() + timedelta(hours=1)).isoformat(), expected_epoch=epoch)


def test_signed_control_and_nonce_replay(service):
    client = installation(service)
    raw = json.dumps({'user_id': 'teacher-1', 'role': 'admin'}).encode()
    path = '/internal/v1/identity/prepare'
    headers = client.headers('POST', path, raw, {'role': 'bridge'})
    with TestClient(client.app) as api:
        assert api.post(path, content=raw).status_code == 401
        assert api.post(path, content=raw, headers=headers).json() == {'epoch': 0}
        assert api.post(path, content=raw, headers=headers).status_code == 401
        assert api.get('/api/classroom/v1/admin/students').status_code == 401


def test_native_proxy_precedes_root_spa_and_never_enrolls_old_token(service, tmp_path, monkeypatch):
    (tmp_path / 'index.html').write_text('native SPA')
    user = types.SimpleNamespace(id='student-1', role='user')
    async def verified(token, redis=None):
        return user
    monkeypatch.setitem(sys.modules, 'open_webui.utils.auth', types.SimpleNamespace(get_verified_user_by_token=verified))
    app = FastAPI()
    app.mount('/', StaticFiles(directory=tmp_path, html=True))
    install_native_routes(app, installation(service))
    with TestClient(app) as browser:
        assert browser.get('/api/classroom/v1/me', headers={'Authorization': 'Bearer old'}).status_code == 401
        issue(service, user.id, 'fresh')
        r = browser.get('/api/classroom/v1/me', headers={'Authorization': 'Bearer fresh'})
        assert r.status_code == 200 and r.json()['user']['id'] == user.id
        service.sessions.revoke_user(user.id)
        assert browser.get('/api/classroom/v1/me', headers={'Authorization': 'Bearer fresh'}).status_code == 401


def test_native_student_unknown_capabilities_denied_teacher_egress_blocked(service):
    client = installation(service)
    async def verified(token):
        return types.SimpleNamespace(id='teacher-1' if token == 'teacher' else 'student-1', role='admin' if token == 'teacher' else 'user')
    issue(service, 'student-1', 'student')
    issue(service, 'teacher-1', 'teacher')
    calls = []
    async def target(scope, receive, send):
        if scope['type'] == 'lifespan':
            return await FastAPI()(scope, receive, send)
        calls.append(scope['path'])
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'{}'})
    app = ClassroomRouteGuardMiddleware(target, client=client, verifier=verified)
    with TestClient(app) as browser:
        for path in ['/api/embeddings', '/api/v1/messages', '/api/message', '/api/new-ai-feature', '/api/v1/chats/test/compact']:
            assert browser.post(path, headers={'Authorization': 'Bearer student'}).status_code == 403
        assert calls == []
        for path in ['/api/embeddings', '/openai/chat/completions', '/ollama/api/generate']:
            assert browser.post(path, headers={'Authorization': 'Bearer teacher'}).status_code == 403
        assert calls == []
        assert browser.get('/api/v1/users/', headers={'Authorization': 'Bearer teacher'}).status_code == 200
        assert '/api/v1/users/' in calls


def test_cookie_mutating_requests_require_matching_origin(service):
    client = installation(service)
    issue(service, 'student-1', 'cookie-token')

    async def verified(token):
        return types.SimpleNamespace(id='student-1', role='user')

    async def target(scope, receive, send):
        if scope['type'] == 'lifespan':
            return await FastAPI()(scope, receive, send)
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'ok'})

    app = ClassroomRouteGuardMiddleware(target, client=client, verifier=verified)
    with TestClient(app) as browser:
        denied = browser.post('/api/v1/files/', headers={'Cookie': 'token=cookie-token'})
        assert denied.status_code == 403
        assert denied.json()['error']['code'] == 'ORIGIN_REQUIRED'
        allowed = browser.post(
            '/api/v1/files/',
            headers={'Cookie': 'token=cookie-token', 'Origin': 'http://testserver', 'Host': 'testserver'},
        )
        assert allowed.status_code == 200


def test_student_websocket_denied_http_ws_also_blocked(service):
    client = installation(service)
    issue(service, 'student-1', 'student')
    issue(service, 'teacher-1', 'teacher')

    async def verified(token):
        return types.SimpleNamespace(
            id='teacher-1' if token == 'teacher' else 'student-1',
            role='admin' if token == 'teacher' else 'user',
        )

    reached = []

    async def target(scope, receive, send):
        if scope['type'] == 'lifespan':
            return await FastAPI()(scope, receive, send)
        reached.append((scope['type'], scope.get('path')))
        if scope['type'] == 'websocket':
            await send({'type': 'websocket.accept'})
            await send({'type': 'websocket.close', 'code': 1000})
            return
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'{}'})

    app = ClassroomRouteGuardMiddleware(target, client=client, verifier=verified)
    with TestClient(app) as browser:
        assert browser.get('/ws/socket.io', headers={'Authorization': 'Bearer student'}).status_code == 403
        assert ('http', '/ws/socket.io') not in reached
        with pytest.raises(Exception):
            with browser.websocket_connect('/ws/socket.io', headers={'Authorization': 'Bearer student'}):
                pass
        assert not any(kind == 'websocket' for kind, _ in reached)
        with browser.websocket_connect('/ws/socket.io', headers={'Authorization': 'Bearer teacher'}):
            pass
        assert ('websocket', '/ws/socket.io') in reached


@pytest.mark.parametrize('uid,role,token', [('student-1', 'user', 'student'), ('teacher-1', 'admin', 'teacher')])
@pytest.mark.parametrize('path', ['/api/chat/completions', '/api/v1/chat/completions'])
def test_native_chat_forces_pipe_before_preprocessing(service, uid, role, token, path):
    client = installation(service)
    issue(service, uid, token)
    async def verified(token):
        return types.SimpleNamespace(id=uid, role=role)
    seen = []
    async def target(scope, receive, send):
        if scope['type'] == 'lifespan':
            return await FastAPI()(scope, receive, send)
        seen.append(json.loads((await receive())['body']))
        assert scope['state']['classroom_identity']['user_id'] == uid
        assert scope['state']['classroom_operation_id'] == 'stable-message'
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'{}'})
    app = ClassroomRouteGuardMiddleware(target, client=client, verifier=verified)
    with TestClient(app) as browser:
        response = browser.post(path, headers={'Authorization': 'Bearer ' + token}, json={
            'model': 'unapproved', 'id': 'stable-message', 'messages': [{'role': 'user', 'content': 'hello'}],
            'features': {'web_search': True}, 'tool_ids': ['arbitrary'], 'background_tasks': {'title_generation': True}, 'direct': True})
        assert response.status_code == 200
        assert seen[0]['model'] == 'classroom_pipe'
        assert seen[0]['background_tasks'] == {} and seen[0]['tool_ids'] == []
        assert 'direct' not in seen[0]
