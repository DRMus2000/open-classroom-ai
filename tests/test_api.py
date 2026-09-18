import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def test_same_origin_api_enforces_identity_and_teacher_role(service):
    from classroom.app.classroom_service.api import create_app

    service.enroll_student("student-1", "学生一", "student1@classroom.local", must_change_password=False)
    student_token = service.sessions.issue("student-1")
    service.register_teacher("teacher-1")
    teacher_token = service.sessions.issue("teacher-1", role="teacher")
    client = TestClient(create_app(service))
    common = {"model": "classroom-default", "messages": [{"role": "user", "content": "hello"}]}
    spoof = client.post("/api/classroom/v1/requests", headers={"Authorization": f"Bearer {student_token}", "Idempotency-Key": "api-op"}, json={"payload": common, "user_id": "teacher-1"})
    assert spoof.status_code == 422
    assert client.get("/api/classroom/v1/admin/requests", headers={"Authorization": f"Bearer {student_token}"}).status_code == 403
    submitted = client.post("/api/classroom/v1/requests", headers={"Authorization": f"Bearer {student_token}", "Idempotency-Key": "api-op"}, json={"payload": common})
    assert submitted.status_code == 200
    queue = client.get("/api/classroom/v1/admin/requests", headers={"Authorization": f"Bearer {teacher_token}"})
    assert queue.status_code == 200 and len(queue.json()["requests"]) == 1
