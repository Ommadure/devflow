"""One error shape for every failure, deliberate or not (spec §8.4):

    {"error": {"code": "SNIPPET_NOT_FOUND", "message": "Snippet not found.",
               "details": {}, "request_id": "b6f1…"}}

Services raise AppError subclasses; the handlers here turn them — and FastAPI's own
validation errors and Starlette's 404/405 — into that shape. Stack traces and internal
messages never reach the client.
"""

from typing import Any, ClassVar

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import current_request_id

log = structlog.get_logger()


class AppError(Exception):
    """An expected failure with a stable, machine-readable code."""

    status_code: ClassVar[int] = 500
    default_code: ClassVar[str] = "INTERNAL_ERROR"
    default_message: ClassVar[str] = "Something went wrong."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)

    def headers(self) -> dict[str, str]:
        return {}


class NotFoundError(AppError):
    status_code = 404
    default_code = "NOT_FOUND"
    default_message = "Not found."


class UnauthorizedError(AppError):
    status_code = 401
    default_code = "UNAUTHORIZED"
    default_message = "Authentication required."

    def headers(self) -> dict[str, str]:
        # RFC 6750: a 401 for a bearer-protected resource names the scheme.
        return {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppError):
    status_code = 403
    default_code = "FORBIDDEN"
    default_message = "Not allowed."


class ConflictError(AppError):
    status_code = 409
    default_code = "CONFLICT"
    default_message = "Conflict."


class ValidationFailedError(AppError):
    status_code = 422
    default_code = "VALIDATION_FAILED"
    default_message = "The request is invalid."


class RateLimitedError(AppError):
    status_code = 429
    default_code = "RATE_LIMITED"
    default_message = "Too many requests. Try again later."

    def __init__(self, retry_after: int, message: str | None = None, **kwargs: Any) -> None:
        details = {"retry_after": max(1, retry_after)}
        super().__init__(message, details=details, **kwargs)

    def headers(self) -> dict[str, str]:
        return {"Retry-After": str(self.details["retry_after"])}


class QuotaExceededError(RateLimitedError):
    default_code = "QUOTA_EXCEEDED"
    default_message = "Daily quota reached."


class UpstreamError(AppError):
    status_code = 502
    default_code = "UPSTREAM_ERROR"
    default_message = "An upstream service failed."


class ServiceUnavailableError(AppError):
    status_code = 503
    default_code = "SERVICE_UNAVAILABLE"
    default_message = "Service temporarily unavailable."


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": current_request_id(),
        }
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        error_body(code, message, details), status_code=status_code, headers=headers
    )


# Starlette raises these for unknown routes and wrong methods; give them stable codes.
_HTTP_CODES = {
    400: ("BAD_REQUEST", "Bad request."),
    404: ("NOT_FOUND", "Not found."),
    405: ("METHOD_NOT_ALLOWED", "Method not allowed."),
    413: ("PAYLOAD_TOO_LARGE", "The request body is too large."),
}


async def _app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers())


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = _HTTP_CODES.get(exc.status_code, (f"HTTP_{exc.status_code}", "Error."))
    headers = dict(exc.headers) if exc.headers else None
    return error_response(exc.status_code, code, message, headers=headers)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default body echoes each invalid `input` back — that would include a
    # rejected password. Keep only where the problem is and what it is.
    fields = [
        {"loc": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return error_response(422, "VALIDATION_FAILED", "The request is invalid.", {"fields": fields})


def register_error_handlers(app: FastAPI) -> None:
    # The decorator form accepts handlers typed for their specific exception class.
    app.exception_handler(AppError)(_app_error)
    app.exception_handler(StarletteHTTPException)(_http_error)
    app.exception_handler(RequestValidationError)(_validation_error)
    # Unhandled exceptions are caught by RequestContextMiddleware, which logs the
    # traceback and returns the generic 500 with the request id.
