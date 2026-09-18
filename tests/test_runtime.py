import time
import threading

import pytest

from classroom.app.classroom_service.runtime import ClassroomRuntime, InstanceLock
from classroom.app.classroom_service.worker import RecordingUpstream
from classroom.app.classroom_service.service import ClassroomService
from classroom.app.classroom_service.database import ClassroomDB


def submit(service, operation):
    r = service.submit('student-1', operation, {'model': 'classroom-default', 'messages': [{'role': 'user', 'content': 'question'}]})
    return service.decide(r['id'], 'teacher-1', 'approve', expected_version=r['version'])


def test_runtime_dispatches_without_pipe_or_manual_worker(service):
    r = submit(service, 'runtime')
    upstream = RecordingUpstream()
    runtime = ClassroomRuntime(service, upstream, interval=0.01)
    runtime.start()
    try:
        deadline = time.monotonic() + 5
        while service.get_request(r['id'])['status'] != 'completed' and time.monotonic() < deadline:
            time.sleep(0.01)
        assert service.get_request(r['id'])['status'] == 'completed'
        assert len(upstream.calls) == 1
        assert service.quota.read('student-1')['reserved'] == 0
    finally:
        runtime.close()


def test_thirty_students_dispatch_once_with_bounded_concurrency(tmp_path):
    db = ClassroomDB(tmp_path / 'thirty.db')
    service = ClassroomService(db, data_root=tmp_path / 'thirty', timezone_name='Asia/Shanghai')
    class SlowProvider(RecordingUpstream):
        active = 0
        peak = 0
        first_wave = threading.Event()
        def generate(self, payload, *, request_id):
            with self._lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
                if self.active == 4: self.first_wave.set()
            try:
                assert self.first_wave.wait(3), 'four configured workers did not enter the provider'
                time.sleep(0.03)
                return super().generate(payload, request_id=request_id)
            finally:
                with self._lock: self.active -= 1
    upstream = SlowProvider()
    for n in range(30):
        uid = 'class-' + str(n)
        service.enroll_student(uid, uid, uid + '@test.invalid', must_change_password=False)
        row = service.submit(uid, 'op-'+str(n), {'model':'classroom-default','messages':[{'role':'user','content':'test'}]})
        service.decide(row['id'], 'teacher', 'approve', expected_version=row['version'])
    runtime = ClassroomRuntime(service, upstream, interval=0.005)
    runtime.start()
    try:
        deadline = time.monotonic() + 8
        while service.db.query_one("SELECT COUNT(*) FROM review_requests WHERE status='completed'")[0] < 30 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert len(upstream.calls) == len({call['request_id'] for call in upstream.calls}) == 30
        assert upstream.peak == 4
        assert service.db.query_one("SELECT COUNT(*) FROM daily_quotas WHERE used=1 AND reserved=0")[0] == 30
        runtime.check_health()
    finally:
        runtime.close()
        db.close()


def test_runtime_recovers_unknown_execution_before_dispatch(service):
    r = submit(service, 'restart')
    claim = service.claim_next('previous-process')
    service.mark_dispatched(r['id'], claim['claim_token'])
    upstream = RecordingUpstream()
    runtime = ClassroomRuntime(service, upstream, interval=0.01)
    runtime.start()
    try:
        assert service.get_request(r['id'])['status'] == 'interrupted_unknown'
        assert service.quota.read('student-1')['reserved'] == 0
        assert upstream.calls == []
        assert service.db.query_one('SELECT dispatch_state FROM execution_attempts WHERE request_id=?', (r['id'],))[0] == 'ended'
    finally:
        runtime.close()


def test_second_instance_cannot_recover_live_owner(tmp_path):
    first = InstanceLock(tmp_path / 'service.lock').acquire()
    try:
        with pytest.raises(RuntimeError):
            InstanceLock(tmp_path / 'service.lock').acquire()
    finally:
        first.close()
    second = InstanceLock(tmp_path / 'service.lock').acquire()
    second.close()


def test_runtime_rejects_clock_rollback_and_ledger_mismatch(service):
    from datetime import timedelta
    runtime = ClassroomRuntime(service, RecordingUpstream())
    runtime.check_health()
    original = service.now()
    service.clock.set(original - timedelta(minutes=10))
    with pytest.raises(RuntimeError, match='backwards'):
        runtime.check_health()
    service.clock.set(original)
    service.quota.read('student-1')
    with service.db.transaction() as db:
        db.execute("UPDATE daily_quotas SET used=1 WHERE user_id='student-1'")
    with pytest.raises(RuntimeError, match='reconciliation'):
        runtime.check_health()
