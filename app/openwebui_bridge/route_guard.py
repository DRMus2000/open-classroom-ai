"""Shared fail-closed route policy helpers (kept aligned with middleware)."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

try:
    from ..classroom_service.errors import ForbiddenError, ValidationError
except ImportError:  # top-level module inside the portable app directory
    from classroom_service.errors import ForbiddenError, ValidationError


STUDENT_MODEL_ROUTES = {"/api/chat/completions", "/api/v1/chat/completions", "/api/chat/completions/"}
DENIED_MODEL_EGRESS_PREFIXES = (
    "/openai/", "/ollama/", "/api/v1/embeddings", "/api/embeddings",
    "/api/v1/messages", "/api/message", "/api/v1/audio", "/api/v1/images",
    "/api/v1/tasks", "/api/tasks", "/api/v1/models", "/api/v1/tools", "/api/v1/functions",
    "/api/v1/retrieval", "/api/v1/knowledge", "/api/v1/web", "/api/v1/configs",
    "/api/completions", "/api/v1/completions",
)


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    route: str
    reason: str
    requires_pipe: bool


class RouteGuard:
    """Authorize routes before any upstream-capable handler runs.

    Runtime enforcement uses ClassroomRouteGuardMiddleware; this class stays as
    the shared allowlist semantics for unit tests and documentation.
    """

    def __init__(self, *, pipe_model: str = "classroom_pipe"):
        self.pipe_model = pipe_model

    def check(self, path: str, *, is_teacher: bool, model: str | None = None,
              classroom_request: bool = False, has_identity: bool = True) -> GuardDecision:
        route = urlsplit(path).path
        if not has_identity:
            raise ForbiddenError("authenticated classroom identity is required", code="IDENTITY_REQUIRED")
        if any(route.startswith(prefix) for prefix in DENIED_MODEL_EGRESS_PREFIXES):
            raise ForbiddenError("模型请求必须经过课堂模型出口", code="DIRECT_MODEL_ROUTE_DENIED")
        if route in STUDENT_MODEL_ROUTES:
            if not classroom_request and not is_teacher:
                raise ForbiddenError("student model calls must use the classroom pipe", code="PIPE_REQUIRED")
            if model != self.pipe_model:
                raise ForbiddenError("仅可选择受管课堂模型", code="MODEL_NOT_ALLOWED")
            return GuardDecision(True, route, "managed classroom pipe", True)
        if any(word in route.lower() for word in ("completion", "generate", "inference", "provider", "search")):
            raise ForbiddenError("unknown model-capable route is disabled", code="UNKNOWN_MODEL_ROUTE")
        return GuardDecision(True, route, "ordinary non-model route", False)

    def assert_payload_safe(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            raise ValidationError("model payload must be an object")
        forbidden = {"tools", "tool_choice", "functions", "function_call", "stream_options", "provider", "base_url", "api_key", "direct", "filter_ids"}
        if forbidden.intersection(payload):
            raise ValidationError("student model control fields are disabled")
