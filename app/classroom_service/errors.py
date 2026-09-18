"""Stable domain errors used by the classroom API and adapters."""

from __future__ import annotations


class ClassroomError(Exception):
    code = "CLASSROOM_ERROR"
    status = 400
    retryable = False

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None,
                 retryable: bool | None = None, request_id: str | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status
        if retryable is not None:
            self.retryable = retryable
        self.request_id = request_id

    def as_dict(self) -> dict:
        result = {
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": bool(self.retryable),
            }
        }
        if self.request_id:
            result["error"]["request_id"] = self.request_id
        return result


class ValidationError(ClassroomError):
    code = "VALIDATION_ERROR"
    status = 422


class AuthenticationError(ClassroomError):
    code = "UNAUTHENTICATED"
    status = 401


class ForbiddenError(ClassroomError):
    code = "FORBIDDEN"
    status = 403


class ConflictError(ClassroomError):
    code = "CONFLICT"
    status = 409


class NotFoundError(ClassroomError):
    code = "NOT_FOUND"
    status = 404


class QuotaError(ClassroomError):
    code = "QUOTA_EXHAUSTED"
    status = 422


class NotReadyError(ClassroomError):
    code = "NOT_READY"
    status = 503
    retryable = True
