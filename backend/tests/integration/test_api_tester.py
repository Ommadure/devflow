import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_resolver
from app.models import AiUsage
from app.services.ai.llm.fake import FakeLLMProvider
from app.services.api_tester.proxy import proxy_http_client
from tests.helpers import InMemoryRateLimiter
from tests.integration.conftest import Headers

PUBLIC = "93.184.216.34"
SEND = "/api/v1/api-tester/send"


@pytest.fixture
async def target_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
        yield client


@pytest.fixture(autouse=True)
def fake_network(app: FastAPI, target_client: httpx.AsyncClient) -> None:
    async def resolve(host: str, port: int) -> list[str]:
        return {"api.example.com": [PUBLIC], "internal.example": ["10.0.0.7"]}[host]

    app.dependency_overrides[get_resolver] = lambda: resolve
    app.dependency_overrides[proxy_http_client] = lambda: target_client


@respx.mock(base_url=f"https://{PUBLIC}")
async def test_send_returns_the_targets_answer_even_an_error(
    respx_mock: respx.MockRouter, api: httpx.AsyncClient, alice: Headers
) -> None:
    respx_mock.get("/missing").respond(404, json={"error": "no such thing"})
    response = await api.post(SEND, json={"url": "https://api.example.com/missing"}, headers=alice)
    assert response.status_code == 200  # the proxy worked; the target said 404
    body = response.json()
    assert (body["status"], body["status_text"], json.loads(body["body"])) == (
        404, "Not Found", {"error": "no such thing"},
    )  # fmt: skip
    assert body["elapsed_ms"] >= 0 and body["size_bytes"] > 0


async def test_private_destinations_are_refused(api: httpx.AsyncClient, alice: Headers) -> None:
    for url in (
        "http://169.254.169.254/latest/meta-data/",
        "https://internal.example/",
        "http://127.0.0.1:8000/health",
    ):
        response = await api.post(SEND, json={"url": url}, headers=alice)
        assert response.status_code == 422, url
        assert response.json()["error"]["code"] == "BLOCKED_DESTINATION"


async def test_the_proxy_has_its_own_rate_limit(
    api: httpx.AsyncClient, alice: Headers, limiter: InMemoryRateLimiter
) -> None:
    me = (await api.get("/api/v1/me", headers=alice)).json()
    limiter.counts[f"proxy:user:{me['id']}"] = 30
    response = await api.post(SEND, json={"url": "https://api.example.com/"}, headers=alice)
    assert response.status_code == 429


async def test_the_tester_needs_a_signed_in_user(api: httpx.AsyncClient) -> None:
    assert (await api.post(SEND, json={"url": "https://api.example.com/"})).status_code == 401


async def test_parse_curl(api: httpx.AsyncClient, alice: Headers) -> None:
    response = await api.post(
        "/api/v1/api-tester/parse-curl",
        json={
            "command": (
                "curl -X PUT https://api.example.com/1 -H 'Accept: application/json' -d '{\"a\":1}'"
            )
        },
        headers=alice,
    )
    assert response.json() == {
        "method": "PUT",
        "url": "https://api.example.com/1",
        "headers": {"Accept": "application/json", "Content-Type": "application/json"},
        "body": '{"a":1}',
        "warnings": [],
    }


async def test_explain_error_is_structured_redacted_and_recorded(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:  # fmt: skip
    llm._script = [
        json.dumps(
            {
                "likely_causes": ["The access token has expired."],
                "suggested_fixes": ["Refresh the token and retry."],
                "confidence": "high",
            }
        )
    ]
    leaked = "sk_live_" + "z" * 24
    response = await api.post(
        "/api/v1/api-tester/explain-error",
        json={
            "method": "GET",
            "url": f"https://api.example.com/v1/charges?api_key={leaked}",
            "status": 401,
            "status_text": "Unauthorized",
            "response_headers": [
                ["WWW-Authenticate", 'Bearer error="invalid_token"'],
                ["Set-Cookie", "s=1"],
            ],
            "response_body": f'{{"error": "token expired", "echo": "{leaked}"}}',
        },
        headers=alice,
    )

    assert response.status_code == 200
    assert response.json()["confidence"] == "high"
    prompt = llm.calls[0][-1].content
    assert leaked not in prompt  # neither from the query string nor echoed in the body
    assert "/v1/charges" in prompt and "?api_key" not in prompt
    assert "WWW-Authenticate" in prompt and "Set-Cookie" not in prompt
    async with sessionmaker() as session:
        [row] = list(await session.scalars(select(AiUsage)))
    assert (row.feature, row.status) == ("explain_http_error", "success")
