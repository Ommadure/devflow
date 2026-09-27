"""Request body size limit and security headers (Phase 7 hardening)."""

from collections.abc import AsyncIterator

import httpx

from app.core.middleware import MAX_REQUEST_BYTES, SECURITY_HEADERS
from tests.integration.conftest import Headers

LOGIN = "/api/v1/auth/login"


def assert_too_large(response: httpx.Response) -> None:
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "PAYLOAD_TOO_LARGE"
    assert error["request_id"] == response.headers["x-request-id"]


async def test_a_declared_oversized_body_is_refused_before_it_is_read(
    api: httpx.AsyncClient,
) -> None:
    # Valid JSON for the route, so only the size can be the reason.
    padding = "x" * MAX_REQUEST_BYTES
    body = f'{{"email": "a@example.com", "password": "{padding}"}}'
    assert_too_large(
        await api.post(LOGIN, content=body, headers={"Content-Type": "application/json"})
    )


async def test_a_chunked_oversized_body_is_refused_while_streaming(
    api: httpx.AsyncClient,
) -> None:
    """No Content-Length: the limit has to count what actually arrives."""

    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"email": "a@example.com", "password": "'
        for _ in range(3 * MAX_REQUEST_BYTES // 65_536):
            yield b"x" * 65_536
        yield b'"}'

    response = await api.post(LOGIN, content=chunks(), headers={"Content-Type": "application/json"})
    assert "content-length" not in response.request.headers  # really chunked
    assert_too_large(response)


async def test_bodies_under_the_limit_still_work(api: httpx.AsyncClient, alice: Headers) -> None:
    # A note at its 200,000-character maximum is well inside the cap.
    response = await api.post(
        "/api/v1/notes", json={"title": "Big", "content": "é" * 200_000}, headers=alice
    )
    assert response.status_code == 201, response.text


async def test_every_response_carries_the_security_headers(
    api: httpx.AsyncClient, alice: Headers
) -> None:
    responses = [
        await api.get("/api/v1/me", headers=alice),  # success
        await api.get("/api/v1/me"),  # 401
        await api.get("/api/v1/nope"),  # 404 from the router
        await api.post(LOGIN, content="x" * (MAX_REQUEST_BYTES + 1)),  # 413 from middleware
    ]
    for response in responses:
        for name, value in SECURITY_HEADERS.items():
            assert response.headers[name] == value, (response.request.url, name)
