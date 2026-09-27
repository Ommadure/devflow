import json
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import GithubInsight
from app.services.ai.llm.fake import FakeLLMProvider
from app.services.github import client as github_client
from tests.conftest import TEST_REDIS_URL
from tests.integration.conftest import Headers

GITHUB = "https://api.github.com"
PROFILE = {
    "login": "octocat",
    "name": "The Octocat",
    "avatar_url": "https://a/x.png",
    "html_url": "https://github.com/octocat",
    "followers": 10,
    "public_repos": 8,
}
REPOS = [
    {
        "name": "hello",
        "html_url": "https://github.com/octocat/hello",
        "description": None,
        "language": "Python",
        "stargazers_count": 3,
        "forks_count": 1,
        "updated_at": "2026-09-20T10:00:00Z",
    }
]
INSIGHT = json.dumps(
    {
        "headline": "A busy week.",
        "highlights": ["11 commits.", "One PR merged."],
        "suggestions": ["Review a PR."],
    }
)


@pytest.fixture
def github() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=GITHUB, assert_all_called=False) as router:
        yield router


def mock_overview(github: respx.MockRouter, **headers: str) -> tuple[respx.Route, respx.Route]:
    profile = github.get("/users/octocat").respond(
        json=PROFILE, headers={"ETag": '"p1"', **headers}
    )
    repos = github.get("/users/octocat/repos").respond(json=REPOS, headers={"ETag": '"r1"'})
    return profile, repos


async def test_overview_is_shaped_and_cached(
    github: respx.MockRouter, api: httpx.AsyncClient, alice: Headers
) -> None:
    profile, repos = mock_overview(github)
    url = "/api/v1/github/overview?username=octocat"

    first = (await api.get(url, headers=alice)).json()
    second = (await api.get(url, headers=alice)).json()

    assert first == second
    assert first["profile"]["login"] == "octocat"
    assert first["repos"][0] == {**REPOS[0], "updated_at": "2026-09-20T10:00:00Z"}
    assert (profile.call_count, repos.call_count) == (1, 1)  # the second came from Redis
    assert repos.calls.last.request.url.params["sort"] == "updated"


async def test_a_stale_cache_is_revalidated_with_the_etag(
    github: respx.MockRouter,
    api: httpx.AsyncClient,
    alice: Headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile, repos = mock_overview(github)
    await api.get("/api/v1/github/overview?username=octocat", headers=alice)
    monkeypatch.setattr(github_client, "FRESH_SECONDS", 0)  # everything is stale now
    profile.respond(304)
    repos.respond(304)

    body = (await api.get("/api/v1/github/overview?username=octocat", headers=alice)).json()

    assert profile.calls.last.request.headers["if-none-match"] == '"p1"'
    assert body["profile"]["name"] == "The Octocat"  # served from cache after the 304


async def test_the_server_token_is_sent(
    github: respx.MockRouter, api: httpx.AsyncClient, alice: Headers, settings: Settings
) -> None:
    from pydantic import SecretStr

    settings.github_token = SecretStr("gh-test-token")
    profile, _ = mock_overview(github)
    await api.get("/api/v1/github/overview?username=octocat", headers=alice)
    assert profile.calls.last.request.headers["authorization"] == "Bearer gh-test-token"


async def test_unknown_users_and_bad_names(
    github: respx.MockRouter, api: httpx.AsyncClient, alice: Headers
) -> None:
    github.get("/users/ghost").respond(404, json={"message": "Not Found"})
    missing = await api.get("/api/v1/github/overview?username=ghost", headers=alice)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "GITHUB_USER_NOT_FOUND")
    bad = await api.get("/api/v1/github/overview?username=../orgs", headers=alice)
    assert bad.json()["error"]["code"] == "INVALID_GITHUB_USERNAME"


async def test_githubs_rate_limit_is_explained(
    github: respx.MockRouter, api: httpx.AsyncClient, alice: Headers
) -> None:
    reset = int(time.time()) + 600
    github.get("/users/octocat").respond(
        403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)}, json={}
    )
    response = await api.get("/api/v1/github/overview?username=octocat", headers=alice)
    assert (response.status_code, response.json()["error"]["code"]) == (429, "GITHUB_RATE_LIMITED")
    assert 590 <= int(response.headers["retry-after"]) <= 600


async def test_setting_the_github_username(api: httpx.AsyncClient, alice: Headers) -> None:
    ok = await api.patch("/api/v1/me", json={"github_username": "octocat"}, headers=alice)
    assert ok.json()["github_username"] == "octocat"
    bad = await api.patch("/api/v1/me", json={"github_username": "not valid"}, headers=alice)
    assert bad.status_code == 422
    cleared = await api.patch("/api/v1/me", json={"github_username": None}, headers=alice)
    assert cleared.json()["github_username"] is None


def push(when: str, size: int) -> dict[str, Any]:
    return {
        "type": "PushEvent",
        "created_at": when,
        "repo": {"name": "octocat/hello"},
        "payload": {"size": size, "commits": [{"message": "SECRET commit message"}]},
    }


async def test_generating_an_insight_sends_numbers_not_content_and_upserts(
    github: respx.MockRouter,
    api: httpx.AsyncClient,
    alice: Headers,
    llm: FakeLLMProvider,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    github.get("/users/octocat/events/public").respond(json=[push(now, 11)])
    await api.patch("/api/v1/me", json={"github_username": "octocat"}, headers=alice)
    llm._script = [INSIGHT, INSIGHT]

    first = await api.post("/api/v1/github/insights/generate", headers=alice)
    await Redis.from_url(TEST_REDIS_URL).flushdb()  # a fresh GitHub fetch for the second run
    await api.post("/api/v1/github/insights/generate", headers=alice)

    assert first.status_code == 201
    assert first.json()["summary"]["headline"] == "A busy week."
    assert first.json()["stats"]["commits"] == 11
    assert "SECRET" not in llm.calls[0][-1].content  # counts only, never commit messages
    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(GithubInsight)) == 1
    listed = (await api.get("/api/v1/github/insights", headers=alice)).json()
    assert [i["summary"]["headline"] for i in listed] == ["A busy week."]


async def test_a_quiet_week_needs_no_model(
    github: respx.MockRouter, api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider
) -> None:
    github.get("/users/octocat/events/public").respond(json=[])
    await api.patch("/api/v1/me", json={"github_username": "octocat"}, headers=alice)
    response = await api.post("/api/v1/github/insights/generate", headers=alice)
    assert response.json()["summary"]["headline"] == "A quiet week on GitHub."
    assert llm.calls == []


async def test_insights_need_a_username_and_are_private(
    github: respx.MockRouter, api: httpx.AsyncClient, alice: Headers, bob: Headers
) -> None:
    missing = await api.post("/api/v1/github/insights/generate", headers=alice)
    assert missing.json()["error"]["code"] == "GITHUB_USERNAME_MISSING"
    github.get("/users/octocat/events/public").respond(json=[])
    await api.patch("/api/v1/me", json={"github_username": "octocat"}, headers=alice)
    await api.post("/api/v1/github/insights/generate", headers=alice)
    assert (await api.get("/api/v1/github/insights", headers=bob)).json() == []
