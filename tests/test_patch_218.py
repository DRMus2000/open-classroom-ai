"""Regressions for the eight findings in the 2.1.8 workspace audit."""
import asyncio
import base64
import hashlib
import io
import json
import sqlite3
import threading
import zipfile
from datetime import timedelta

import httpx
import pytest
from PIL import Image

from classroom.app.classroom_service.ai_auditor import AIAuditor, parse_audit_decision
from classroom.app.classroom_service.api import InternalAuthenticator, create_app
from classroom.app.classroom_service.canonical import payload_digest
from classroom.app.classroom_service.database import ClassroomDB, MIGRATIONS
from classroom.app.classroom_service.errors import ConflictError
from classroom.app.classroom_service.migrate import migrate
from classroom.app.classroom_service.runtime import ClassroomRuntime
from classroom.app.classroom_service.service import ClassroomService
from classroom.app.classroom_service.worker import ClassroomWorker, HttpUpstream, RecordingUpstream, UpstreamError
from classroom.app.openwebui_bridge.client import BridgeClient


def question():
    return {'model': 'classroom-default', 'messages': [{'role': 'user', 'content': 'Please review the attached task'}]}


def test_final_decision_excludes_reasoning_examples(service):
    raw = '<think>Sample {"decision":"approve","reason":"example"}</think>\n{"decision":"reject","reason":"final"}'
    assert parse_audit_decision(raw) == ('reject', 'final')
    service.set_review_mode('teacher-1', 'ai', 0)
    row = service.submit('student-1', 'final-decision', question())
    AIAuditor(service, RecordingUpstream(default=[raw])).tick()
    assert service.get_request(row['id'])['status'] == 'rejected'


@pytest.mark.parametrize('raw', [
    '{"decision":"approve"}\n{"decision":"reject"}',
    '<think>{"decision":"approve"}',
    '{"decision":"approve","decision":"reject"}',
    '"decision":"approve", "reason":"truncated',
    '{"result":{"decision":"approve"}',
])
def test_ambiguous_decision_falls_back_to_teacher(service, raw):
    service.set_review_mode('teacher-1', 'ai', 0)
    row = service.submit('student-1', 'ambiguous', question())
    AIAuditor(service, RecordingUpstream(default=[raw])).tick()
    fresh = service.get_request(row['id'])
    assert fresh['status'] == 'pending' and fresh['review_channel'] == 'teacher'
    assert service.quota.read('student-1')['used'] == 0


def test_text_attachment_is_audited_in_full(service):
    service.set_review_mode('teacher-1', 'ai', 0)
    content = 'begin\n' + ('x' * 5000) + '\nEND_OF_ATTACHMENT'
    file = service.attachments.add('student-1', 'task.txt', content.encode())
    payload = {**question(), 'attachments': [{'id': file['id'], 'sha256': file['sha256']}]}
    row = service.submit('student-1', 'attachment', payload)
    upstream = RecordingUpstream(default=['{"decision":"approve","reason":"ok"}'])
    AIAuditor(service, upstream).tick()
    audited = json.loads(upstream.calls[0]['payload']['messages'][-1]['content'])
    assert 'END_OF_ATTACHMENT' in json.dumps(audited)
    provider = RecordingUpstream()
    ClassroomWorker(service, provider).run_one()
    assert audited['待审对话（含本次附件全文）'] == provider.calls[0]['payload']['messages'][1:]
    assert service.get_request(row['id'])['status'] == 'completed'


@pytest.mark.parametrize('kind', ['image', 'long_text'])
def test_unreviewable_attachment_goes_to_teacher(service, kind):
    service.set_review_mode('teacher-1', 'ai', 0)
    if kind == 'image':
        buffer = io.BytesIO()
        Image.new('RGB', (1, 1)).save(buffer, format='PNG')
        file = service.attachments.add('student-1', 'task.png', buffer.getvalue())
    else:
        file = service.attachments.add('student-1', 'task.txt', b'x' * 41000)
    row = service.submit('student-1', kind, {**question(), 'attachments': [{'id': file['id'], 'sha256': file['sha256']}]})
    upstream = RecordingUpstream(default=['{"decision":"approve"}'])
    AIAuditor(service, upstream).tick()
    result = service.get_request(row['id'])
    assert result['status'] == 'pending' and result['review_channel'] == 'teacher'
    assert not upstream.calls


@pytest.mark.parametrize('legacy', [False, True])
def test_retry_survives_prompt_change_without_new_reservation(service, legacy):
    payload = question()
    row = service.submit('student-1', 'same-op', payload, chat_id='chat')
    if legacy:
        digest = payload_digest('student-1', 'same-op', {
            **row['original_payload'], 'attachments': [], 'attachment_ids': [],
            'chat_id': 'chat', 'user_message_id': None, 'assistant_message_id': None, 'parent_request_id': None})
        with service.db.transaction() as db:
            db.execute('UPDATE review_requests SET client_payload_digest=? WHERE id=?', (digest, row['id']))
    service.set_system_prompt('teacher-1', 'Updated classroom instruction', 0)
    retry = service.submit('student-1', 'same-op', payload, chat_id='chat')
    assert retry['id'] == row['id']
    assert retry['original_payload'] == row['original_payload']
    assert service.quota.read('student-1')['reserved'] == 1
    with pytest.raises(ConflictError):
        service.submit('student-1', 'same-op', {**payload, 'messages': [{'role': 'user', 'content': 'different'}]}, chat_id='chat')


def test_slow_audit_does_not_block_generation(tmp_path):
    db = ClassroomDB(tmp_path / 'runtime.db')
    service = ClassroomService(db, data_root=tmp_path, timezone_name='Asia/Shanghai')
    for uid in ('s1', 's2'):
        service.enroll_student(uid, uid, uid + '@a.b', must_change_password=False)
    row = service.submit('s1', 'approved', question())
    service.decide(row['id'], 'teacher', 'approve', expected_version=row['version'])
    service.set_review_mode('teacher', 'ai', 0)
    service.submit('s2', 'auditing', question())
    entered, release, generated = threading.Event(), threading.Event(), threading.Event()

    class Upstream:
        def generate(self, payload, *, request_id):
            if request_id.startswith('audit-'):
                entered.set()
                assert release.wait(5)
                yield '{"decision":"approve"}'
            else:
                generated.set()
                yield 'answer'

    runtime = ClassroomRuntime(service, Upstream(), interval=0.01)
    try:
        runtime.start()
        assert entered.wait(3)
        assert generated.wait(3), 'generation waited for an unrelated audit'
    finally:
        release.set()
        runtime.close()
        db.close()


def test_non_stream_audit_has_total_timeout_and_prefers_final_content():
    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{'
            await asyncio.Event().wait()

    upstream = HttpUpstream('https://fixture.invalid/v1', lambda: 'fake', total_timeout=0.05,
                            transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=SlowBody())))
    with pytest.raises(UpstreamError):
        list(upstream.generate({**question(), 'stream': False}, request_id='audit-timeout'))
    assert not upstream._active
    upstream.transport = httpx.MockTransport(lambda req: httpx.Response(200, json={'choices': [{
        'message': {'content': 'Unable to decide', 'reasoning_content': '{"decision":"approve"}'}, 'finish_reason': 'stop'}]}))
    assert ''.join(upstream.generate({**question(), 'stream': False}, request_id='audit-final')) == 'Unable to decide'


def test_shutdown_cancels_inflight_audit(tmp_path):
    entered, closed = threading.Event(), threading.Event()

    class WaitingBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b''

        async def aclose(self):
            closed.set()

    db = ClassroomDB(tmp_path / 'shutdown.db')
    service = ClassroomService(db, data_root=tmp_path, timezone_name='Asia/Shanghai')
    service.enroll_student('s', 'S', 's@a.b', must_change_password=False)
    service.set_review_mode('teacher', 'ai', 0)
    row = service.submit('s', 'stop-audit', question())
    upstream = HttpUpstream('https://fixture.invalid/v1', lambda: 'fake', total_timeout=2,
                            transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=WaitingBody())))
    runtime = ClassroomRuntime(service, upstream, interval=0.01)
    try:
        runtime.start()
        assert entered.wait(3)
    finally:
        runtime.close()
    assert closed.is_set() and not upstream._active
    assert service.get_request(row['id'])['status'] == 'pending'
    assert service.quota.read('s')['used'] == 0
    db.close()


def test_teacher_upload_and_native_file_link_without_student_roster(service):
    from types import SimpleNamespace
    secret = b't' * 32
    upstream = RecordingUpstream()
    app = create_app(service, internal_auth=InternalAuthenticator(secret), bridge_only=True,
                     runtime=SimpleNamespace(worker=SimpleNamespace(upstream=upstream)))
    bridge = BridgeClient('http://127.0.0.1:8790', secret)
    fp = hashlib.sha256(b'fixture-teacher').hexdigest()
    service.sessions.session_issued('teacher-1', fp, native_expires_at=(service.now() + timedelta(hours=1)).isoformat(), expected_epoch=0)

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=bridge.base_url) as client:
            identity = {'user_id': 'teacher-1', 'role': 'admin', 'token_fingerprint': fp}
            async def post(path, body, principal=identity):
                raw = json.dumps(body).encode()
                return await client.post(path, content=raw, headers=bridge.headers('POST', path, raw, principal))
            uploaded = await post('/api/classroom/v1/attachments', {'filename': 'example.py', 'content_base64': base64.b64encode(b'print(1)').decode()})
            assert uploaded.status_code == 200
            aid = uploaded.json()['id']
            linked = await post('/internal/v1/identity/file-linked', {'user_id': 'teacher-1', 'native_file_id': 'f1', 'attachment_id': aid}, {'role': 'bridge'})
            assert linked.status_code == 200
            resolved = await post('/internal/v1/identity/files-resolve', {'user_id': 'teacher-1', 'native_file_ids': ['f1'], 'operation_id': 'teacher-op'}, {'role': 'bridge'})
            assert resolved.status_code == 200 and resolved.json()['attachments'][0]['id'] == aid
            answer = await post('/api/classroom/v1/admin/chat/completions', {**question(), 'attachments': resolved.json()['attachments']})
            assert answer.status_code == 200 and '[DONE]' in answer.text
            assert 'print(1)' in json.dumps(upstream.calls[-1]['payload'])
            service.clock.set(service.now() + timedelta(hours=25))
            assert service.attachments.cleanup_temporary() == 0
            assert service.attachments.get(aid)['content'] == b'print(1)'
    asyncio.run(run())
    assert service.db.query_one("SELECT COUNT(*) FROM students WHERE user_id='teacher-1'")[0] == 0
    assert service.db.query_one("SELECT COUNT(*) FROM daily_quotas WHERE user_id='teacher-1'")[0] == 0


def test_v4_upgrade_preserves_attachment_rows_and_native_links(tmp_path):
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as db:
        for version, script in MIGRATIONS.items():
            if version > 4:
                break
            db.executescript(script)
            db.execute('INSERT INTO schema_migrations VALUES(?,?,?)', (version, hashlib.sha256(script.encode()).hexdigest(), 'fixture'))
            db.commit()
        db.execute("INSERT INTO students(user_id,roster_name,login_identifier,created_at,updated_at) VALUES('s','S','s@a.b','now','now')")
        db.execute("INSERT INTO security_states(user_id,updated_at) VALUES('s','now')")
        db.execute("INSERT INTO attachments(id,owner_user_id,original_filename,media_type,size_bytes,sha256,blob_ref,created_at) VALUES('a','s','a.txt','text/plain',1,'hash','blobs/a','now')")
        db.execute("INSERT INTO native_attachments VALUES('s','f','a')")
        db.execute("INSERT INTO native_attachment_copies VALUES('s','op','f','a')")
        before = db.execute('SELECT * FROM attachments').fetchall()
    upgraded = ClassroomDB(path)
    assert [tuple(row) for row in upgraded.query_all('SELECT * FROM attachments')] == before
    assert tuple(upgraded.query_one('SELECT * FROM native_attachments')) == ('s', 'f', 'a')
    assert tuple(upgraded.query_one('SELECT * FROM native_attachment_copies')) == ('s', 'op', 'f', 'a')
    assert not upgraded.query_all('PRAGMA foreign_key_check')
    upgraded.close()
    assert migrate(str(path), verify_only=True)['schema_version'] == 5
    ClassroomDB(path).close()


def test_share_hosts_excludes_loopback(monkeypatch):
    from classroom.app.classroom_service import network
    monkeypatch.setattr(network.socket, 'getaddrinfo', lambda *a, **k: [
        (2, 1, 6, '', (ip, 0)) for ip in ('127.0.0.1', '0.0.0.0', '169.254.1.1', '192.168.1.10', '192.168.1.10')])
    assert network.share_hosts() == ['192.168.1.10']


def test_patch_archive_is_program_only_and_hash_verified(tmp_path):
    from classroom.app.build_patch import build, PREFIX, PATCH_ID
    archive_path = tmp_path / 'patch.zip'
    result = build(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        manifest_name = PREFIX + 'patch-manifest-' + PATCH_ID + '.json'
        manifest = json.loads(archive.read(manifest_name))
        assert set(archive.namelist()) == {PREFIX + name for name in manifest['files']} | {manifest_name}
        assert 'app/classroom_service/database.py' in manifest['files']
        assert 'web/teacher/guest-link.js' in manifest['files']
        assert 'PATCH_2.1.8_README.md' in manifest['files']
        for name, digest in manifest['files'].items():
            assert not name.startswith(('runtime/', 'data/', 'release/'))
            assert not name.endswith(('.db', '.pyc', '.env', '.key'))
            assert hashlib.sha256(archive.read(PREFIX + name)).hexdigest() == digest
    assert result['sha256'] == hashlib.sha256(archive_path.read_bytes()).hexdigest()
    before = archive_path.read_bytes()
    with pytest.raises(ValueError):
        build(archive_path)
    assert archive_path.read_bytes() == before
