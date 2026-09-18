"""Guest access settings and guest chat system-prompt injection."""
import asyncio
import hashlib
import json
from datetime import timedelta

import httpx
import pytest

from classroom.app.classroom_service.api import create_app, InternalAuthenticator
from classroom.app.classroom_service.errors import AuthenticationError, ForbiddenError, ValidationError
from classroom.app.classroom_service.guest_chat import GuestChat
from classroom.app.classroom_service.worker import RecordingUpstream
from classroom.app.openwebui_bridge.client import BridgeClient


def _bridge(service):
    key = b'g' * 32
    app = create_app(service, internal_auth=InternalAuthenticator(key), bridge_only=True, runtime=None)
    return BridgeClient('http://127.0.0.1:8790', key), app, key


def test_guest_access_toggle_rotate_and_verify(service):
    before = service.get_guest_access()
    assert before['enabled'] is False and before['has_token'] is False
    opened = service.set_guest_access('teacher-1', enabled=True, expected_version=before['version'], rotate=True)
    assert opened['enabled'] and opened['has_token'] and opened['token'] and opened['share_url_path'].startswith('/classroom/guest/?t=')
    assert service.verify_guest_token(opened['token'])
    closed = service.set_guest_access('teacher-1', enabled=False, expected_version=opened['version'])
    assert closed['enabled'] is False
    assert not service.verify_guest_token(opened['token'])
    reopened = service.set_guest_access('teacher-1', enabled=True, expected_version=closed['version'])
    assert reopened['enabled'] and service.verify_guest_token(opened['token'])
    rotated = service.set_guest_access('teacher-1', enabled=True, expected_version=reopened['version'], rotate=True)
    assert rotated['token'] != opened['token']
    assert not service.verify_guest_token(opened['token'])
    assert service.verify_guest_token(rotated['token'])


def test_guest_chat_injects_system_prompt(service):
    class FakeRuntime:
        def __init__(self, upstream):
            self.worker = type('W', (), {'upstream': upstream})()

    service.set_ready(True)
    service.set_system_prompt('teacher-1', '访客须先提出引导问题。', service.get_system_prompt()['version'])
    upstream = RecordingUpstream(default=['访客回答'])
    chat = GuestChat(service, FakeRuntime(upstream), max_concurrency=64)
    response = chat.response({'model': 'classroom-default', 'messages': [{'role': 'user', 'content': '什么是循环？'}]})

    async def collect():
        chunks = []
        async for part in response.body_iterator:
            chunks.append(part.decode() if isinstance(part, bytes) else part)
        return ''.join(chunks)

    body = asyncio.run(collect())
    assert '访客回答' in body
    assert upstream.calls
    messages = upstream.calls[0]['payload']['messages']
    assert messages[0]['role'] == 'system'
    assert messages[0]['content'] == '访客须先提出引导问题。'
    last = messages[-1]['content']
    assert last == '什么是循环？' or last == [{'type': 'text', 'text': '什么是循环？'}]


def test_guest_chat_rejects_over_1000_chars(service):
    service.set_ready(True)
    chat = GuestChat(service, type('R', (), {'worker': type('W', (), {'upstream': RecordingUpstream()})()})())
    with pytest.raises(ValidationError, match='1000'):
        chat.response({'model': 'classroom-default', 'messages': [{'role': 'user', 'content': 'x' * 1001}]})


def test_guest_chat_respects_classroom_pause(service):
    service.set_ready(True)
    service.set_classroom_paused('teacher-1', True, 'exam')
    chat = GuestChat(service, type('R', (), {'worker': type('W', (), {'upstream': RecordingUpstream()})()})())
    with pytest.raises(ForbiddenError):
        chat.response({'model': 'classroom-default', 'messages': [{'role': 'user', 'content': 'hi'}]})


def test_guest_http_endpoints(service):
    bridge, app, key = _bridge(service)
    opened = service.set_guest_access('teacher-1', enabled=True, expected_version=0, rotate=True)
    token = opened['token']

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=bridge.base_url) as client:
            bad = await client.post('/internal/v1/guest/validate', content=b'{}', headers=bridge.headers(
                'POST', '/internal/v1/guest/validate', b'{}', {'role': 'bridge'}))
            assert bad.status_code == 401
            raw = json.dumps({'token': token}).encode()
            ok = await client.post('/internal/v1/guest/validate', content=raw, headers=bridge.headers(
                'POST', '/internal/v1/guest/validate', raw, {'role': 'bridge'}))
            assert ok.status_code == 200
            guest_headers = bridge.headers(
                'GET', '/api/classroom/v1/guest/status', b'',
                {'role': 'guest', 'user_id': 'guest', 'guest_token': token})
            status = await client.get('/api/classroom/v1/guest/status', headers=guest_headers)
            assert status.status_code == 200
            assert status.json()['ok'] is True
            service.set_guest_access('teacher-1', enabled=False, expected_version=opened['version'])
            denied = await client.get('/api/classroom/v1/guest/status', headers=guest_headers)
            assert denied.status_code == 401

    asyncio.run(run())
