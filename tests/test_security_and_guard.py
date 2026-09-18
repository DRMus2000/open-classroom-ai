import pytest

from classroom.app.classroom_service.auth import SessionManager
from classroom.app.classroom_service.errors import AuthenticationError, ForbiddenError, ValidationError
from classroom.app.classroom_service.canonical import normalize_payload
from classroom.app.openwebui_bridge.route_guard import RouteGuard


def test_session_revoke_invalidates_old_token(service):
    token = service.sessions.issue("student-1")
    assert service.sessions.validate(token).user_id == "student-1"
    service.sessions.revoke_user("student-1", actor_id="teacher-1")
    with pytest.raises(AuthenticationError):
        service.sessions.validate(token)


def test_first_password_state_blocks_generation(service):
    service.enroll_student("must-change", "新学生", "new@classroom.local", must_change_password=True)
    with pytest.raises(ForbiddenError):
        service.submit("must-change", "op", {"model": "classroom-default", "messages": [{"role": "user", "content": "hi"}]})


def test_route_guard_denies_direct_model_and_requires_managed_pipe():
    guard = RouteGuard()
    with pytest.raises(ForbiddenError):
        guard.check("/openai/chat/completions", is_teacher=False, model="classroom_pipe", classroom_request=False)
    with pytest.raises(ForbiddenError):
        guard.check("/api/embeddings", is_teacher=True, model="classroom_pipe", classroom_request=False)
    with pytest.raises(ForbiddenError):
        guard.check("/api/chat/completions", is_teacher=False, model="other", classroom_request=True)
    assert guard.check("/api/chat/completions", is_teacher=False, model="classroom_pipe", classroom_request=True).requires_pipe
    with pytest.raises(ValidationError):
        guard.assert_payload_safe({"messages": [], "model": "classroom_pipe", "tools": []})


def test_remote_image_urls_are_not_accepted():
    with pytest.raises(ValidationError):
        normalize_payload({"model": "classroom-default", "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://example.invalid/image.png"}}]}]})
