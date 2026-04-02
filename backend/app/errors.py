from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException


@dataclass(frozen=True, slots=True)
class ErrorPayload:
    code: str
    message: str
    detail: str | None = None


class AppError(Exception):
    status_code = 500
    code = "app_error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def payload(self) -> ErrorPayload:
        return ErrorPayload(code=self.code, message=self.message, detail=self.detail)


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class PolicyViolationError(AppError):
    status_code = 403
    code = "policy_violation"


class AccessDeniedError(AppError):
    status_code = 403
    code = "access_denied"


class ResourceNotReadyError(AppError):
    status_code = 503
    code = "resource_not_ready"


class ModelInvocationError(AppError):
    status_code = 502
    code = "model_invocation_error"


def to_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, AppError):
        payload = exc.payload()
        return HTTPException(
            status_code=exc.status_code,
            detail={
                "code": payload.code,
                "message": payload.message,
                "detail": payload.detail,
            },
        )

    return HTTPException(
        status_code=500,
        detail={
            "code": "internal_error",
            "message": str(exc),
        },
    )
