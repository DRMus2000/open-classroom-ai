"""Hardening: audit isolation/timeouts, v5 preflight, share adapters, attachment retention."""
import asyncio
import hashlib
import sqlite3
import threading
import time
from datetime import timedelta

import httpx
import pytest

from classroom.app.classroom_service import network
from classroom.app.classroom_service.ai_auditor import (
    AIAuditor, AUDIT_RESPONSE_FORMAT, HANDOFF_IMAGE, HANDOFF_TOO_LONG, HANDOFF_TIMEOUT,
)
from classroom.app.classroom_service.database import ClassroomDB, MIGRATIONS
from classroom.app.classroom_service.runtime import ClassroomRuntime
from classroom.app.classroom_service.schema_v5 import PREFLIGHT_CODE, repair_v5_identities
from classroom.app.classroom_service.service import ClassroomService
from classroom.app.classroom_service.worker import HttpUpstream, RecordingUpstream, UpstreamError


def question():
    return {'model': 'classroom-default', 'messages': [{'role': 'user', 'content': 'Please review the attached task'}]}


def test_complete_timeout_does_not_use_first_output_timeout():
    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{'
            await asyncio.Event().wait()

    started = time.monotonic()
    upstream = HttpUpstream(
        'https://fixture.invalid/v1', lambda: 'fake', first_output_timeout=0.05,
        complete_timeout=0.25, complete_read_timeout=0.25,
        transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=SlowBody())))
    with pytest.raises(UpstreamError):
        list(upstream.generate({**question(), 'stream': False}, request_id='audit-independent'))
    elapsed = time.monotonic() - started
    assert elapsed >= 0.15
    assert elapsed < 2


def test_audit_retry_budget_shrinks(service, monkeypatch):
    from classroom.app.classroom_service import ai_auditor
    monkeypatch.setattr(ai_auditor, 'AUDIT_BUDGET_SECONDS', 2.5)
    monkeypatch.setattr(ai_auditor, 'AUDIT_READ_TIMEOUT', 2.0)
    timeouts = []

    class SlowFail:
        def generate(self, payload, *, request_id, total_timeout=None, read_timeout=None):
            timeouts.append(total_timeout)
            raise UpstreamError('ConnectTimeout')

    service.set_review_mode('teacher-1', 'ai', 0)
    row = service.submit('student-1', 'budget', question())
    AIAuditor(service, SlowFail()).tick()
    fresh = service.get_request(row['id'])
    assert fresh['review_channel'] == 'teacher'
    assert HANDOFF_TIMEOUT in (fresh.get('decision_note') or '')
    assert timeouts and timeouts[0] <= 2.6
    assert any(later < timeouts[0] for later in timeouts[1:])


def test_unreviewable_reasons_are_explicit(service):
    import io
    from PIL import Image
    service.set_review_mode('teacher-1', 'ai', 0)
    buffer = io.BytesIO()
    Image.new('RGB', (1, 1)).save(buffer, format='PNG')
    image = service.attachments.add('student-1', 'task.png', buffer.getvalue())
    row = service.submit('student-1', 'img', {**question(), 'attachments': [{'id': image['id'], 'sha256': image['sha256']}]})
    AIAuditor(service, RecordingUpstream(default=['{"decision":"approve"}'])).tick()
    assert service.get_request(row['id'])['decision_note'] == HANDOFF_IMAGE
    long_file = service.attachments.add('student-2', 'task.txt', b'x' * 41000)
    row = service.submit('student-2', 'long', {**question(), 'attachments': [{'id': long_file['id'], 'sha256': long_file['sha256']}]})
    AIAuditor(service, RecordingUpstream(default=['{"decision":"approve"}'])).tick()
    assert service.get_request(row['id'])['decision_note'] == HANDOFF_TOO_LONG


def test_structured_output_then_plain_retry(service):
    class Gateway:
        def __init__(self):
            self.calls = []
        def generate(self, payload, *, request_id, **kwargs):
            self.calls.append(payload)
            if payload.get('response_format'):
                raise UpstreamError('provider rejected complete request (400): unknown field response_format')
            return ['{"decision":"approve","reason":"ok"}']

    service.set_review_mode('teacher-1', 'ai', 0)
    row = service.submit('student-1', 'schema', question())
    upstream = Gateway()
    AIAuditor(service, upstream).tick()
    assert service.get_request(row['id'])['status'] == 'approved_queued'
    assert upstream.calls[0]['response_format'] == AUDIT_RESPONSE_FORMAT
    assert 'response_format' not in upstream.calls[1]


def test_multiple_json_still_not_retried(service):
    service.set_review_mode('teacher-1', 'ai', 0)
    row = service.submit('student-1', 'multi', question())
    upstream = RecordingUpstream(default=['{"decision":"approve"}\n{"decision":"reject"}'])
    AIAuditor(service, upstream).tick()
    assert len(upstream.calls) == 1
    assert service.get_request(row['id'])['review_channel'] == 'teacher'


def test_audit_isolation_keeps_generation_running(tmp_path):
    db = ClassroomDB(tmp_path / 'iso.db')
    service = ClassroomService(db, data_root=tmp_path, timezone_name='Asia/Shanghai')
    service.enroll_student('s1', 'S1', 's1@a.b', must_change_password=False)
    service.enroll_student('s2', 'S2', 's2@a.b', must_change_password=False)
    approved = service.submit('s1', 'approved', question())
    service.decide(approved['id'], 'teacher', 'approve', expected_version=approved['version'])
    service.set_review_mode('teacher', 'ai', 0)
    service.submit('s2', 'audit', question())

    def boom():
        raise RuntimeError('prompt store exploded')
    service.get_audit_system_prompt = boom
    generated = threading.Event()

    class Upstream:
        def generate(self, payload, *, request_id, **kwargs):
            generated.set()
            yield 'answer'

    runtime = ClassroomRuntime(service, Upstream(), interval=0.01)
    try:
        runtime.start()
        assert generated.wait(3)
        other = service.db.query_one("SELECT id FROM review_requests WHERE user_id='s2'")['id']
        deadline = time.time() + 3
        while time.time() < deadline and service.get_request(other)['review_channel'] != 'teacher':
            time.sleep(0.05)
        assert service.get_request(other)['review_channel'] == 'teacher'
        assert service.ready_report()['ready'] is True
        assert service.ready_report()['ai_audit_paused'] is False
    finally:
        runtime.close()
        db.close()


def test_three_isolation_failures_pause_ai_review(service):
    service.set_review_mode('teacher-1', 'ai', 0)
    def boom():
        raise RuntimeError('isolated')
    service.get_audit_system_prompt = boom
    for index in range(3):
        row = service.submit('student-1', f'iso-{index}', question())
        assert AIAuditor(service, RecordingUpstream()).tick() is True
        service.cancel(row['id'], 'student-1')
    assert service.ai_audit_paused() is True
    fourth = service.submit('student-1', 'iso-4', question())
    assert fourth['review_channel'] == 'teacher'
    service.set_review_mode('teacher-1', 'ai', service.get_review_mode()['version'])
    assert service.ai_audit_paused() is False


def test_corrupt_audit_fault_stops_runtime(tmp_path):
    db = ClassroomDB(tmp_path / 'corrupt.db')
    service = ClassroomService(db, data_root=tmp_path, timezone_name='Asia/Shanghai')
    service.enroll_student('s', 'S', 's@a.b', must_change_password=False)
    service.set_review_mode('teacher', 'ai', 0)
    service.submit('s', 'audit', question())
    service.get_audit_system_prompt = lambda: (_ for _ in ()).throw(sqlite3.DatabaseError('database disk image is malformed'))
    runtime = ClassroomRuntime(service, RecordingUpstream(), interval=0.01)
    try:
        runtime.start()
        deadline = time.time() + 3
        while time.time() < deadline and service.ready_report()['ready']:
            time.sleep(0.05)
        assert service.ready_report()['ready'] is False
        assert runtime.failure == 'DatabaseError'
    finally:
        runtime.close()
        db.close()


def _v4_db(path, *, owner='s', with_security=True, with_student=True):
    with sqlite3.connect(path) as db:
        for version, script in MIGRATIONS.items():
            if version > 4:
                break
            db.executescript(script)
            db.execute('INSERT INTO schema_migrations VALUES(?,?,?)', (version, hashlib.sha256(script.encode()).hexdigest(), 'fixture'))
        if with_student:
            db.execute("INSERT INTO students(user_id,roster_name,login_identifier,created_at,updated_at) VALUES(?,?,?,?,?)",
                       ('s', 'S', 's@a.b', 'now', 'now'))
        if with_security:
            db.execute("INSERT INTO security_states(user_id,updated_at) VALUES('s','now')")
        db.execute("INSERT INTO attachments(id,owner_user_id,original_filename,media_type,size_bytes,sha256,blob_ref,created_at) VALUES('a',?,'a.txt','text/plain',1,'hash','blobs/a','now')", (owner,))
        db.execute("INSERT INTO native_attachments VALUES(?,?,?)", (owner, 'f', 'a'))
        db.commit()


def test_v5_preflight_blocks_and_repair_backfills_student(tmp_path):
    path = tmp_path / 'dirty.db'
    _v4_db(path, with_security=False)
    with pytest.raises(RuntimeError, match=PREFLIGHT_CODE):
        ClassroomDB(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] == 4
    preview = repair_v5_identities(path, apply=False)
    assert preview['ready_for_v5'] is False
    assert 's' in preview['gaps']['repairable_students']
    applied = repair_v5_identities(path, apply=True)
    assert applied['ready_for_v5'] is True
    upgraded = ClassroomDB(path)
    assert upgraded.query_one("SELECT user_id FROM security_states WHERE user_id='s'")[0] == 's'
    upgraded.close()


def test_v5_repair_does_not_invent_unknown_identities(tmp_path):
    path = tmp_path / 'ghost.db'
    _v4_db(path, owner='ghost', with_student=False, with_security=False)
    result = repair_v5_identities(path, apply=True)
    assert result['ready_for_v5'] is False
    assert result['gaps']['unknown'] == ['ghost']
    assert result['repaired'] == []
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM security_states").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM attachments").fetchone()[0] == 1


def test_share_interfaces_rank_physical_before_vpn(monkeypatch):
    monkeypatch.setattr(network, 'adapter_interfaces', lambda: [
        {'address': '10.8.0.2', 'name': 'NordLynx', 'kind': 'vpn'},
        {'address': '192.168.1.10', 'name': '以太网', 'kind': 'physical'},
        {'address': '172.28.16.1', 'name': 'vEthernet Docker', 'kind': 'virtual'},
    ])
    hosts = network.share_hosts()
    assert hosts[0] == '192.168.1.10'
    assert hosts[-1] == '172.28.16.1'
    kinds = [item['kind'] for item in network.share_interfaces()]
    assert kinds == ['physical', 'vpn', 'virtual']


def test_teacher_attachments_follow_reference_and_inflight(service):
    service.register_teacher('teacher-1')
    dangling = service.attachments.add('teacher-1', 'old.py', b'print(0)')
    linked = service.attachments.add('teacher-1', 'keep.py', b'print(1)')
    inflight = service.attachments.add('teacher-1', 'busy.py', b'print(2)')
    with service.db.transaction() as db:
        db.execute("INSERT INTO native_attachments(user_id,native_file_id,attachment_id) VALUES('teacher-1','f',?)", (linked['id'],))
    service.attachments.begin_use([inflight['id']])
    service.clock.set(service.now() + timedelta(hours=25))
    assert service.attachments.cleanup_temporary() == 1
    with pytest.raises(Exception):
        service.attachments.get(dangling['id'])
    assert service.attachments.get(linked['id'])['content'] == b'print(1)'
    assert service.attachments.get(inflight['id'])['content'] == b'print(2)'
    report = service.attachments.storage_report()
    assert report['referenced']['count'] == 1
    assert report['in_flight']['count'] == 1
    service.attachments.end_use([inflight['id']])
    assert service.attachments.cleanup_temporary() == 1
    assert service.attachments.storage_report()['unreferenced']['count'] == 0
