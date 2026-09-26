"""Request context: a request id on every log line, response and error body, plus one
access log per request and the catch-all for unhandled exceptions.

Written as plain ASGI middleware rather than Starlette's BaseHTTPMiddleware, which
buffers responses and would break Server-Sent Events streaming in Phase 5.
"""

import time

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response
from app.core.logging import new_context, request_id_from

log = structlog.get_logger()


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = request_id_from(Headers(scope=scope).get("x-request-id"))
        new_context(request_id=request_id, path=scope["path"])
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            log.exception("request.unhandled_error")
            if response_started:
                raise  # headers already sent; nothing clean left to say
            response = error_response(500, "INTERNAL_ERROR", "Something went wrong.")
            await response(scope, receive, send_with_request_id)
        finally:
            log.info(
                "request",
                method=scope["method"],
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
