from datetime import datetime, timedelta, timezone

from classroom.app.classroom_service.clock import iso


def payload(text):
    return {"model": "classroom-default", "messages": [{"role": "user", "content": text}]}


def test_worker_lease_expiry_releases_without_retry(service):
    request = service.submit("student-1", "op", payload("lease"))
    request = service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])
    claim = service.claim_next(lease_seconds=10)
    # Move the test clock beyond the lease without sending an upstream call.
    service.clock.set(service.now() + timedelta(seconds=11))
    assert service.reconcile_leases() == 1
    final = service.get_request(request["id"])
    assert final["status"] == "interrupted_unknown" and final["charge_units"] == 0
    assert service.claim_next() is None


def test_max_concurrency_is_a_hard_local_limit(service):
    service.max_concurrency = 1
    first = service.submit("student-1", "one", payload("one"))
    first = service.decide(first["id"], "teacher-1", "approve", expected_version=first["version"])
    second = service.submit("student-2", "two", payload("two"))
    second = service.decide(second["id"], "teacher-1", "approve", expected_version=second["version"])
    assert service.claim_next() is not None
    assert service.claim_next() is None


def test_model_profile_change_returns_approved_work_to_review(service):
    request = service.submit("student-1", "op", payload("profile"))
    request = service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])
    result = service.set_allowed_models("teacher-1", {"classroom-v2"})
    assert result["invalidated_approved"] == 1
    assert service.get_request(request["id"])["status"] == "pending"
