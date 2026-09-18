import pytest
from classroom.app.classroom_service.errors import ConflictError, ValidationError
from classroom.app.classroom_service.worker import ClassroomWorker, RecordingUpstream


def test_system_prompt_version_validation_and_snapshot_scope(service):
    before = service.get_system_prompt()
    assert before['version'] == 0
    changed = service.set_system_prompt('teacher-1', '先提一个引导问题，不直接给答案。', before['version'])
    first = service.submit('student-1', 'prompt-original', {'model':'classroom-default', 'messages':[{'role':'user','content':'解释循环'}]}, chat_id='chat-a')
    assert first['original_payload']['messages'][0]['content'] == changed['prompt']
    service.decide(first['id'], 'teacher-1', 'approve', expected_version=first['version'])
    worker = ClassroomWorker(service, RecordingUpstream(default=['第一轮回答']))
    worker.run_one()
    service.set_system_prompt('teacher-1', '新的课堂要求：使用简短例子。', changed['version'])
    follow = service.submit('student-1', 'prompt-follow', {'model':'classroom-default','messages':[{'role':'user','content':'继续'}]}, chat_id='chat-a', parent_request_id=first['id'])
    assert follow['original_payload']['messages'][0]['content'] == changed['prompt']
    fresh = service.submit('student-2','prompt-new', {'model':'classroom-default','messages':[{'role':'user','content':'新问题'}]}, chat_id='chat-b')
    assert fresh['original_payload']['messages'][0]['content'] == '新的课堂要求：使用简短例子。'
    with pytest.raises(ConflictError):
        service.set_system_prompt('teacher-1','旧页面覆盖',0)
    for invalid in ['', '   ', 'x'*20001, None]:
        with pytest.raises(ValidationError):
            service.set_system_prompt('teacher-1',invalid,2)


def test_system_prompt_teacher_only_http(service):
    import asyncio
    from classroom.app.classroom_service.api import create_app, InternalAuthenticator
    from classroom.app.openwebui_bridge.client import BridgeClient
    import hashlib, httpx, json
    from datetime import timedelta
    key=b'p'*32
    app=create_app(service, internal_auth=InternalAuthenticator(key), bridge_only=True)
    bridge=BridgeClient('http://127.0.0.1:8790',key)
    async def request(uid,role,method,body=None):
        fingerprint=hashlib.sha256(uid.encode()).hexdigest()
        service.sessions.session_issued(uid,fingerprint,native_expires_at=(service.now()+timedelta(hours=1)).isoformat(),expected_epoch=0)
        path='/api/classroom/v1/admin/system-prompt';raw=json.dumps(body).encode() if body else b''
        headers=bridge.headers(method,path,raw,{'user_id':uid,'role':role,'token_fingerprint':fingerprint})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=bridge.base_url) as c:
            return await c.request(method,path,content=raw,headers=headers)
    assert asyncio.run(request('student-1','user','GET')).status_code==403
    assert asyncio.run(request('student-1','user','PUT',{'prompt':'override','expected_version':0})).status_code==403
    r=asyncio.run(request('teacher-1','admin','GET'))
    assert r.status_code==200
    assert asyncio.run(request('teacher-1','admin','PUT',{'prompt':'课堂测试提示词','expected_version':r.json()['version']})).status_code==200
