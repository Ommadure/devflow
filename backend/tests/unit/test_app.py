"""App-wide behaviour without a database: error shape, request ids, probes, CORS."""

from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from app.api.routes.health import get_readiness_checks
from tests.helpers import ORIGIN


@pytest.fixture
def boom_app(app: FastAPI) -> Iterator[FastAPI]:
    class Body(BaseModel):
        password: str
        age: int

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    @app.post("/echo")
    async def echo(body: Body) -> Body:
        return body

    yield app


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_every_response_carries_a_request_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert len(response.headers["x-request-id"]) == 16


async def test_a_sane_upstream_request_id_is_reused(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


async def test_an_unsafe_request_id_is_replaced(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "bad\nid"})
    assert response.headers["x-request-id"] != "bad\nid"


async def test_unknown_route_uses_the_error_shape(client: httpx.AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == response.headers["x-request-id"]


async def test_wrong_method_uses_the_error_shape(client: httpx.AsyncClient) -> None:
    response = await client.delete("/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


async def test_validation_errors_never_echo_the_input(boom_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=boom_app), base_url="https://test"
    ) as client:
        response = await client.post("/echo", json={"password": "hunter2", "age": "old"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert error["details"]["fields"][0]["loc"] == "body.age"
    assert "hunter2" not in response.text


async def test_unhandled_errors_become_a_generic_500(boom_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=boom_app), base_url="https://test"
    ) as client:
        response = await client.get("/boom")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error["request_id"] == response.headers["x-request-id"]
    assert "hunter2" not in response.text


async def test_ready_when_every_check_passes(app: FastAPI, client: httpx.AsyncClient) -> None:
    async def ok() -> None:
        return None

    app.dependency_overrides[get_readiness_checks] = lambda: {"database": ok, "redis": ok}
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


async def test_not_ready_names_the_failed_dependency(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    async def ok() -> None:
        return None

    async def down() -> None:
        raise ConnectionError("refused")

    app.dependency_overrides[get_readiness_checks] = lambda: {"database": down, "redis": ok}
    response = await client.get("/ready")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "NOT_READY"
    assert error["details"]["checks"] == {"database": "error", "redis": "ok"}


async def test_cors_allows_only_configured_origins(client: httpx.AsyncClient) -> None:
    preflight = {"Access-Control-Request-Method": "POST"}
    allowed = await client.options("/api/v1/me", headers={"Origin": ORIGIN, **preflight})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    denied = await client.options(
        "/api/v1/me", headers={"Origin": "https://evil.test", **preflight}
    )
    assert "access-control-allow-origin" not in denied.headers
