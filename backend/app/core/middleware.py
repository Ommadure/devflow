"""Request context (a request id on every log line, response and error body, one access
log per request, security headers, the catch-all for unhandled exceptions) and the request
body size limit.

Written as plain ASGI middleware rather than Starlette's BaseHTTPMiddleware, which
buffers responses and would break Server-Sent Events streaming in Phase 5.
"""

import time

import structlog
from fastapi import HTTPException
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response
from app.core.logging import new_context, request_id_from

log = structlog.get_logger()

# The largest legitimate body is an API-tester request (≤ 1,000,000 characters of body plus
# JSON escaping); notes are ≤ 200,000 characters. Caddy enforces the same cap in production.
MAX_REQUEST_BYTES = 2 * 1024 * 1024

# Every response is one user's data or a token: no cache (a CDN, a shared proxy, the
# browser's back button) may keep a copy. The rest stop a JSON response ever being
# sniffed into HTML, framed, or leaking its URL in a Referer. setdefault: a route that
# sets its own value wins.
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


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
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
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


class BodySizeLimitMiddleware:
    """Refuse request bodies over `max_bytes` with 413, before they are buffered.

    With a Content-Length the answer comes before a byte of the body is read (the server
    never delivers more than the declared length). A chunked body has no length up front,
    so it is counted as the app reads it; FastAPI re-raises an HTTPException raised while
    it reads the body, and the usual handler turns it into the standard error shape.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            if declared.isdigit() and int(declared) > self.max_bytes:
                await _too_large()(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        received = 0

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status_code=413)
            return message

        await self.app(scope, counting_receive, send)


def _too_large() -> ASGIApp:
    return error_response(413, "PAYLOAD_TOO_LARGE", "The request body is too large.")
