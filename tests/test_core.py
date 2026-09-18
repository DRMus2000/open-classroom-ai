from datetime import datetime, timezone

import pytest

from classroom.app.classroom_service.attachments import AttachmentStore
from classroom.app.classroom_service.clock import local_date_and_next_midnight
from classroom.app.classroom_service.errors import ClassroomError, ConflictError, ForbiddenError, QuotaError, ValidationError
from classroom.app.classroom_service.worker import ClassroomWorker, RecordingUpstream, UnknownOutcome


def payload(text="hello"):
    return {"model": "classroom-default", "messages": [{"role": "user", "content": text}]}


def test_question_over_1000_chars_is_rejected(service):
    accepted = service.submit("student-1", "op-1000-ok", payload("x" * 1000))
    assert accepted["status"] == "pending"
    with pytest.raises(ValidationError, match="1000"):
        service.submit("student-1", "op-1000-over", payload("x" * 1001))


def test_pending_reserves_rejection_consumes_without_upstream(service):
    request = service.submit("student-1", "op-1", payload())
    assert request["status"] == "pending"
    assert service.quota.read("student-1")["reserved"] == 1
    rejected = service.decide(request["id"], "teacher-1", "reject", expected_version=request["version"], note="请补充说明")
    assert rejected["status"] == "rejected"
    quota = service.quota.read("student-1")
    assert (quota["used"], quota["reserved"], quota["available"]) == (1, 0, 2)


def test_approve_worker_settles_once_and_replay_does_not_call_twice(service):
    request = service.submit("student-1", "op-1", payload())
    request = service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])
    upstream = RecordingUpstream(default=["a", "b"])
    worker = ClassroomWorker(service, upstream)
    result = worker.run_one()
    assert result["status"] == "completed"
    assert len(upstream.calls) == 1
    assert service.get_request(request["id"])["output_text"] == "ab"
    assert service.quota.read("student-1")["used"] == 1
    assert service.submit("student-1", "op-1", payload())["id"] == request["id"]
    assert len(upstream.calls) == 1


def test_same_operation_different_payload_is_conflict(service):
    service.submit("student-1", "op-1", payload("original"))
    with pytest.raises(ConflictError):
        service.submit("student-1", "op-1", payload("changed"))


def test_one_active_request_and_quota_exhaustion(service):
    first = service.submit("student-1", "op-1", payload())
    with pytest.raises(ConflictError):
        service.submit("student-1", "op-2", payload("second"))
    service.decide(first["id"], "teacher-1", "reject", expected_version=first["version"])
    for i in range(2, 4):
        request = service.submit("student-1", f"op-{i}", payload(str(i)))
        service.decide(request["id"], "teacher-1", "reject", expected_version=request["version"])
    with pytest.raises(QuotaError):
        service.submit("student-1", "op-4", payload("fourth"))


def test_cross_day_pending_expires_and_new_day_starts(service):
    request = service.submit("student-1", "op-1", payload())
    service.clock.set(datetime(2026, 9, 8, 16, 1, tzinfo=timezone.utc))  # 00:01 next day in Shanghai
    assert service.quota.expire_pending(when=service.now()) == 1
    assert service.get_request(request["id"])["status"] == "expired"
    assert service.quota.read("student-1")["date"] == "2026-09-09"
    assert service.quota.read("student-1")["reserved"] == 0


def test_teacher_adjustment_is_batch_atomic_and_idempotent(service):
    result = service.quota.adjust_many(["student-1", "student-2"], delta=1, actor_id="teacher-1", reason="练习", operation_key="adjust-1")
    assert [r["after"]["adjustment"] for r in result["rows"]] == [1, 1]
    again = service.quota.adjust_many(["student-1", "student-2"], delta=1, actor_id="teacher-1", reason="练习", operation_key="adjust-1")
    assert again == result
    with pytest.raises(ClassroomError):
        service.quota.adjust_many(["student-1", "student-2"], delta=2, actor_id="teacher-1", reason="练习", operation_key="adjust-1")
    with pytest.raises(ClassroomError):
        service.quota.adjust_many(["student-1", "missing"], delta=1, actor_id="teacher-1", reason="bad", operation_key="adjust-2")
    assert service.quota.read("student-1")["adjustment"] == 1


def test_service_uses_detected_timezone_when_not_explicitly_configured():
    from classroom.app.classroom_service import ClassroomDB, ClassroomService

    app = ClassroomService(ClassroomDB(), data_root=".pytest-classroom-data")
    assert app.quota.timezone_name == app.timezone_name


def test_upstream_failure_releases_without_charge(service):
    request = service.submit("student-1", "op-1", payload())
    request = service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])
    worker = ClassroomWorker(service, RecordingUpstream(error=RuntimeError("offline")))
    result = worker.run_one()
    assert result["status"] == "interrupted"
    assert result["charge_units"] == 0
    assert service.quota.read("student-1")["used"] == 0


def test_unknown_provider_outcome_is_not_retried(service):
    request = service.submit("student-1", "op-1", payload())
    request = service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])
    upstream = RecordingUpstream(error=UnknownOutcome("connection lost after send"))
    worker = ClassroomWorker(service, upstream)
    assert worker.run_one()["status"] == "interrupted_unknown"
    assert worker.run_one() is None
    assert len(upstream.calls) == 1


def test_student_stop_charges_only_after_visible_output(service):
    request = service.submit("student-1", "op-1", payload())
    request = service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])
    claimed = service.claim_next()
    service.mark_dispatched(request["id"], claimed["claim_token"])
    service.cancel(request["id"], "student-1", source="student")
    service.finalize(request["id"], outcome="interrupted", reason="executor closed")
    assert service.quota.read("student-1")["used"] == 0
    request2 = service.submit("student-1", "op-2", payload("second"))
    request2 = service.decide(request2["id"], "teacher-1", "approve", expected_version=request2["version"])
    claimed2 = service.claim_next(); service.mark_dispatched(request2["id"], claimed2["claim_token"])
    service.append_event(request2["id"], "delta", {"text": "partial"})
    service.record_delivery(request2["id"], "student-1", 2, consumer_id="verified-chat")
    stopped = service.cancel(request2["id"], "student-1", source="student")
    stopped = service.finalize(request2["id"], outcome="interrupted", reason="executor closed")
    assert stopped["status"] == "stopped_by_student_after_output"
    assert service.quota.read("student-1")["used"] == 1


def valid_png():
    import io
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, "PNG")
    return buffer.getvalue()


def test_image_and_python_attachment_are_validated_and_archived(service):
    png = valid_png()
    image = service.attachments.add("student-1", "diagram.png", png)
    code = service.attachments.add("student-1", "lesson.py", "print('hello')\n".encode())
    request = service.submit("student-1", "op-1", {"model": "classroom-default", "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "attachment:" + image["id"]}}]}], "attachments": [{"id": image["id"], "sha256": image["sha256"]}, {"id": code["id"], "sha256": code["sha256"]}]}, attachment_ids=[image["id"], code["id"]])
    assert request["status"] == "pending"
    assert len(request["attachments"]) == 2
    assert service.attachments.get(code["id"], user_id="student-1")["content"].startswith(b"print")
    approved = service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])
    upstream = RecordingUpstream(default=["ok"])
    ClassroomWorker(service, upstream).run_one()
    provider_payload = upstream.calls[0]["payload"]
    assert "attachments" not in provider_payload
    assert "data:image/png;base64," in str(provider_payload)
    assert "print('hello')" in str(provider_payload)


def test_attachment_digest_is_bound_to_the_immutable_blob(service):
    png = valid_png()
    image = service.attachments.add("student-1", "diagram.png", png)
    with pytest.raises(ConflictError):
        service.submit("student-1", "bad-digest", {"model": "classroom-default", "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "attachment:" + image["id"]}}]}], "attachments": [{"id": image["id"], "sha256": "0" * 64}]}, attachment_ids=[image["id"]])
