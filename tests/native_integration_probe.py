"""Run real native authentication routes against synthetic, isolated accounts."""
import os, sys, tempfile, pathlib, asyncio, json, hashlib
root = pathlib.Path(tempfile.mkdtemp(prefix='classroom-native-auth-'))
os.environ.update(DATA_DIR=str(root/'native'), DATABASE_URL='sqlite:///'+str(root/'webui.db'), WEBUI_SECRET_KEY='test-only-native-auth-signing-key-32bytes', ENABLE_DB_MIGRATIONS='false', FROM_INIT_PY='true', OFFLINE_MODE='true', HF_HUB_OFFLINE='1')
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'app'))
import httpx
import open_webui.main as native
from open_webui.internal.db import Base, engine
from open_webui.models.auths import Auths
from open_webui.utils.auth import get_password_hash
from classroom_service.database import ClassroomDB
from classroom_service.service import ClassroomService
from classroom_service.api import create_app, InternalAuthenticator
from openwebui_bridge.client import BridgeClient
from openwebui_bridge.native_routes import install_native_routes
from openwebui_bridge.auth_hooks import install_auth_hooks
from openwebui_bridge.file_hook import install_file_hook
from openwebui_bridge.middleware import ClassroomRouteGuardMiddleware
from openwebui_bridge.policy import install_policy_hook
from classroom_service.runtime import ClassroomRuntime
from classroom_service.worker import RecordingUpstream
Base.metadata.create_all(engine)
service = ClassroomService(ClassroomDB(root/'classroom.db'), data_root=root/'classroom', timezone_name='Asia/Shanghai')
key=b'n'*32
upstream=RecordingUpstream(default=['Approved native answer'])
runtime=ClassroomRuntime(service,upstream,interval=0.02)
internal=create_app(service,internal_auth=InternalAuthenticator(key),bridge_only=True,runtime=runtime)
class LocalBridge(BridgeClient):
    async def download(self, path, principal, *, method='GET', body=None):
        if self._http is None:
            self._http = httpx.AsyncClient(transport=httpx.ASGITransport(app=internal), base_url=self.base_url)
        return await super().download(path, principal, method=method, body=body)
    async def request(self, method, path, *, principal, body=None, raw=None, extra_headers=None):
        raw=json.dumps(body).encode() if body is not None and raw is None else raw or b''
        headers=self.headers(method,path,raw,principal)
        headers.update({k:v for k,v in (extra_headers or {}).items() if k.lower()=='idempotency-key'})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=internal),base_url=self.base_url) as c:
            return await c.request(method,path,headers=headers,content=raw)
bridge=LocalBridge('http://127.0.0.1:8790',key)
install_native_routes(native.app,bridge)
install_auth_hooks(native.app,bridge)
install_file_hook(native.app,bridge)
native.app.add_middleware(ClassroomRouteGuardMiddleware,client=bridge)
native.app.state.redis=None
install_policy_hook(native)
for route in native.app.router.routes:
    if getattr(route,'path','')=='/api/chat/completions':
        original_chat=route.dependant.call
        async def observed_chat(**kwargs):
            print('CHAT_INPUT_CONTRACT',kwargs['form_data'].get('model'),getattr(kwargs['request'].state,'classroom_identity',{}).get('role'),flush=True)
            return await original_chat(**kwargs)
        route.dependant.call=observed_chat
async def main():
    await native.seed_registered_defaults()
    await native.initialize_runtime_config(native.app)
    teacher=await Auths.insert_new_auth('teacher@test.invalid',await get_password_hash('Teacher-test-123'), 'Teacher', role='admin')
    student=await Auths.insert_new_auth('student@test.invalid',await get_password_hash('Student-test-123'), 'Student', role='user')
    service.enroll_student(student.id,'Student',student.email,must_change_password=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=native.app),base_url='http://testserver') as c:
        r=await c.post('/api/v1/auths/signin',json={'email':student.email,'password':'Student-test-123'})
        assert r.status_code==200,(r.status_code,r.text[:300])
        old=r.json()['token']; h={'Authorization':'Bearer '+old}
        assert (await c.get('/api/classroom/v1/me',headers=h)).json()['must_change_password'] is True
        assert (await c.post('/api/v1/files/',headers=h,files={'file':('x.txt',b'x')})).status_code==428
        assert (await c.post('/api/v1/auths/update/password',headers=h,json={'password':'Student-test-123','new_password':'Student-test-123'})).status_code==400
        r=await c.post('/api/v1/auths/update/password',headers=h,json={'password':'Student-test-123','new_password':'Changed-test-456'})
        assert r.status_code==200,(r.status_code,r.text[:300])
        assert (await c.get('/api/classroom/v1/me',headers=h)).status_code==401
        r=await c.post('/api/v1/auths/signin',json={'email':student.email,'password':'Changed-test-456'})
        assert r.status_code==200,(r.status_code,r.text[:300])
        fresh=r.json()['token']; h={'Authorization':'Bearer '+fresh}
        assert (await c.get('/api/classroom/v1/me',headers=h)).json()['must_change_password'] is False
        r=await c.post('/api/v1/files/?process=true',headers=h,files={'file':('example.py',b'print("never executed")','text/plain')})
        assert r.status_code==200,(r.status_code,r.text[:300])
        fid=r.json()['id']
        refs=await bridge.control('identity/files-resolve',{'user_id':student.id,'native_file_ids':[fid],'operation_id':'upload-contract'})
        assert service.attachments.get(refs['attachments'][0]['id'])['content']==b'print("never executed")'
        for path in ['/api/embeddings','/api/v1/messages','/api/message']:
            assert (await c.post(path,headers=h,json={})).status_code==403
        r=await c.post('/api/v1/auths/signin',json={'email':teacher.email,'password':'Teacher-test-123'})
        assert r.status_code==200,(r.status_code,r.text[:300])
        th={'Authorization':'Bearer '+r.json()['token']}
        from open_webui.models.config import Config
        await Config.upsert({'openai.enable': False, 'ollama.enable': False})
        code=(pathlib.Path(__file__).resolve().parents[1]/'app/openwebui_classroom_pipe.py').read_text(encoding='utf-8-sig')
        r=await c.post('/api/v1/functions/create',headers=th,json={'id':'classroom_pipe','name':'Classroom','content':code,'meta':{'description':'isolated probe'}})
        assert r.status_code==200,(r.status_code,r.text[:300])
        r=await c.post('/api/v1/functions/id/classroom_pipe/toggle',headers=th)
        assert r.status_code==200,(r.status_code,r.text[:300])
        r=await c.post('/api/classroom/bootstrap-complete',headers=th,json={})
        assert r.status_code==200,(r.status_code,r.text[:300])
        runtime.start()
        try:
            task=asyncio.create_task(c.post('/api/chat/completions',headers=h,json={'id':'native-answer-1','parent_id':None,'model':'unapproved-client-model','files':[{'id':fid,'type':'file'}],'messages':[{'role':'user','content':'native question'}], 'user_message':{'id':'native-user-1','role':'user','content':'native question'},'stream':True}))
            pending=None
            for _ in range(400):
                pending=service.db.query_one("SELECT id,version FROM review_requests WHERE status='pending'")
                if pending or task.done():
                    break
                await asyncio.sleep(0.05)
            if not pending:
                r=await task
                raise AssertionError(('native chat did not reach approval',r.status_code,r.text[:700],list(native.app.state.MODELS)))
            assert upstream.calls==[]
            assert service.get_request(pending['id'])['attachments'], 'native file did not reach review'
            r=await c.post('/api/classroom/v1/admin/requests/'+pending['id']+'/decision',headers=th,json={'decision':'approve','expected_version':pending['version']})
            assert r.status_code==200,(r.status_code,r.text[:300])
            r=await asyncio.wait_for(task,15)
            assert r.status_code==200,(r.status_code,r.text[:700])
            # Native saved chats consume the Pipe and persist output via their
            # event emitter; the HTTP response is not the answer SSE stream.
            from open_webui.models.chats import Chats
            classroom_request=service.get_request(pending['id'])
            native_message=await Chats.get_message_by_id_and_message_id(classroom_request['chat_id'],'native-answer-1')
            assert native_message and 'Approved native answer' in json.dumps(native_message), native_message
            assert len(upstream.calls)==1
            assert service.get_request(pending['id'])['status']=='completed'
            r=await c.post('/api/chat/completions', headers=th, json={
                'id':'teacher-answer-1', 'model':'classroom_pipe',
                'messages':[{'role':'user','content':'teacher question'}],
                'user_message':{'id':'teacher-user-1','role':'user','content':'teacher question'}, 'stream':True})
            assert r.status_code==200, (r.status_code,r.text[:700])
            assert len(upstream.calls)==2, r.text[:700]
            assert upstream.calls[-1]['request_id'].startswith('teacher-')
            assert 'Approved native answer' in r.text and '[DONE]' in r.text, r.text[:700]
            assert service.db.query_one('SELECT COUNT(*) FROM students WHERE user_id=?',(teacher.id,))[0]==0
            print('NATIVE_TEACHER_CHAT_OK')
        finally:
            await asyncio.to_thread(runtime.close)
        r=await c.post('/api/v1/users/'+student.id+'/update',headers=th,json={'password':'Reset-test-789'})
        assert r.status_code==200,(r.status_code,r.text[:300])
        assert (await c.get('/api/classroom/v1/me',headers=h)).status_code==401
        r=await c.post('/api/v1/auths/signin',json={'email':student.email,'password':'Reset-test-789'})
        assert r.status_code==200,(r.status_code,r.text[:300])
        assert (await c.get('/api/classroom/v1/me',headers={'Authorization':'Bearer '+r.json()['token']})).json()['must_change_password'] is True
    print('NATIVE_AUTH_FILE_CHAT_CONTRACT_OK')
asyncio.run(main())
if os.environ.get('CLASSROOM_PROBE_MIGRATION') == '1':
    import subprocess, zipfile
    from prepare_installation import snapshot
    from classroom_service.archive import ClassroomExporter
    snapshot(root/'webui.db', root/'native/webui.db')
    destination=root/'migrated'
    subprocess.run([sys.executable,'-B',str(pathlib.Path(__file__).resolve().parents[1]/'app/prepare_installation.py'),
                    '--native-root',str(root/'native'),'--destination',str(destination)],check=True,capture_output=True)
    migrated=ClassroomService(ClassroomDB(destination/'classroom/classroom.db'),data_root=destination/'classroom',timezone_name='Asia/Shanghai')
    archive=ClassroomExporter(migrated,destination/'exports').export('probe-teacher')
    with zipfile.ZipFile(archive) as bundle:
        files=[name for name in bundle.namelist() if name.startswith('legacy/attachments/')]
        assert len(files)==1
        assert bundle.read(files[0])==b'print("never executed")'
    migrated.db.close()
    print('NATIVE_LEGACY_FILE_MIGRATION_EXPORT_OK')
