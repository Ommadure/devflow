"""Structured logging with structlog.

Production and CI emit one JSON object per line, which log platforms can search by field.
Local development uses a coloured console renderer because humans read those logs.

Context is bound once per unit of work — a request (request_id, path, user_id) or, from
Phase 4, a background task — and every line logged underneath carries it. Passwords,
tokens and cookies are never logged.
"""

import logging
import re
import sys
import uuid

import sentry_sdk
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, get_contextvars
from structlog.typing import EventDict, WrappedLogger

from app.core.config import AppEnv

# Fields worth searching by; also copied onto Sentry events as tags.
CONTEXT_KEYS = ("request_id", "path", "user_id", "task")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def new_context(**values: object) -> None:
    """Start a fresh unit of work: drop whatever the last one bound, bind these."""
    clear_contextvars()
    bind_context(**values)


def bind_context(**values: object) -> None:
    """Add fields to the current unit of work's context (None values are skipped)."""
    bind_contextvars(**{k: v for k, v in values.items() if v is not None})


def current_request_id() -> str | None:
    value = get_contextvars().get("request_id")
    return str(value) if value is not None else None


def request_id_from(header: str | None) -> str:
    """Reuse an upstream proxy's request id if it looks sane, else make one.
    (A client-supplied header is untrusted: never let it inject into logs.)"""
    return header if header and _SAFE_REQUEST_ID.match(header) else uuid.uuid4().hex[:16]


def configure_logging(app_env: AppEnv, level: str = "INFO") -> None:
    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer()
        if app_env == "development"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            report_logged_errors,  # before format_exc_info turns the exception into text
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def report_logged_errors(_: WrappedLogger, method: str, event_dict: EventDict) -> EventDict:
    """`log.error(...)` / `log.exception(...)` also reach Sentry (when it's configured).

    The catch-all handler turns an unhandled exception into a clean 500, which would
    otherwise hide it from Sentry.
    """
    if method in ("error", "exception", "critical") and sentry_sdk.get_client().is_active():
        exc_info = event_dict.get("exc_info")
        error = sys.exc_info()[1] if exc_info is True else exc_info
        if isinstance(error, BaseException):
            sentry_sdk.capture_exception(error)
        else:
            sentry_sdk.capture_message(str(event_dict.get("event")), level="error")
    return event_dict
