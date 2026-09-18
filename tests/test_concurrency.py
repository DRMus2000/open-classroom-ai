from concurrent.futures import ThreadPoolExecutor

from classroom.app.classroom_service.errors import ClassroomError
from classroom.app.classroom_service.worker import ClassroomWorker, RecordingUpstream


def payload(text="hello"):
    return {"model": "classroom-default", "messages": [{"role": "user", "content": text}]}


def test_concurrent_same_operation_is_idempotent(service):
    def submit(_):
        try:
            return service.submit("student-1", "same-op", payload())
        except Exception as exc:
            return exc
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(submit, range(10)))
    successes = [r for r in results if isinstance(r, dict)]
    assert len(successes) == 10
    assert len({r["id"] for r in successes}) == 1
    assert service.quota.read("student-1")["reserved"] == 1


def test_concurrent_distinct_operations_have_one_active_request(service):
    def submit(i):
        try:
            return service.submit("student-1", f"op-{i}", payload(str(i)))
        except Exception as exc:
            return exc
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(submit, range(10)))
    assert len([r for r in results if isinstance(r, dict)]) == 1
    assert len([r for r in results if isinstance(r, ClassroomError)]) == 9


def test_concurrent_decision_and_claim_only_one_wins(service):
    request = service.submit("student-1", "op", payload())
    def decide(_):
        try:
            return service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])
        except Exception as exc:
            return exc
    with ThreadPoolExecutor(max_workers=2) as pool:
        decisions = list(pool.map(decide, range(2)))
    assert len([r for r in decisions if isinstance(r, dict)]) == 1
    def claim(_):
        try:
            return service.claim_next()
        except Exception as exc:
            return exc
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, range(2)))
    assert len([r for r in claims if isinstance(r, dict)]) == 1
    assert len([r for r in claims if r is None]) == 1
