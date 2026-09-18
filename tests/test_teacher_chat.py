import hashlib
import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace

import httpx

from classroom.app.classroom_service.api import create_app, InternalAuthenticator
from classroom.app.classroom_service.worker import RecordingUpstream


def test_teacher_chat_authorization_history_and_no_student_quota(service):
    upstream = RecordingUpstream(default=['Teacher answer'])
    # Only the production lifespan is replaced here; exercise the real signed
    # HTTP boundary, native session validation and provider payload creation.
    runtime = SimpleNamespace(worker=SimpleNamespace(upstream=upstream))
    auth = InternalAuthenticator(b't' * 32)
    app = create_app(service, internal_auth=auth, bridge_only=True, runtime=runtime)
    service.set_ready(True)
    from classroom.app.openwebui_bridge.client import BridgeClient
    bridge = BridgeClient('http://127.0.0.1:8790', b't' * 32)
    async def request(uid, role, payload):
        fingerprint = hashlib.sha256(uid.encode()).hexdigest()
        service.sessions.session_issued(uid, fingerprint,
            native_expires_at=(service.now()+timedelta(hours=1)).isoformat(), expected_epoch=0)
        path = '/api/classroom/v1/admin/chat/completions'
        raw = json.dumps(payload).encode()
        headers = bridge.headers('POST', path, raw, {'user_id':uid,'role':role,'token_fingerprint':fingerprint})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=bridge.base_url) as client:
            return await client.post(path, content=raw, headers=headers)
    payload = {'model':'classroom-default','messages':[
        {'role':'user','content':'first question'}, {'role':'assistant','content':'first answer'},
        {'role':'user','content':'follow up'}]}
    assert asyncio.run(request('student-1','user',payload)).status_code == 403
    assert not upstream.calls
    r = asyncio.run(request('teacher-1','admin',payload))
    assert r.status_code == 200 and 'Teacher answer' in r.text and '[DONE]' in r.text
    assert len(upstream.calls) == 1
    assert upstream.calls[0]['payload']['messages'][0]['content'] == 'first question'
    assert service.db.query_one("SELECT COUNT(*) FROM students WHERE user_id='teacher-1'")[0] == 0
    assert service.db.query_one('SELECT COUNT(*) FROM review_requests')[0] == 0
    assert asyncio.run(request('teacher-1','admin',{**payload,'model':'unapproved'})).status_code == 403
    assert len(upstream.calls) == 1
