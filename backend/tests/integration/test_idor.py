"""IDOR (Insecure Direct Object Reference): can one user reach another's data by id?

For every resource, Bob tries to read, change and delete Alice's row. Each attempt must
answer exactly like a row that doesn't exist — same status, same code — so Bob can't even
learn that the id is real (ADR 0002). And Alice's row must be untouched afterwards.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from tests.integration.conftest import Headers


@dataclass(frozen=True)
class Resource:
    url: str
    create: dict[str, Any]
    change: dict[str, Any]
    search_url: str


RESOURCES = {
    "snippet": Resource(
        "/api/v1/snippets",
        {"title": "Alice's secret", "code": "API_KEY = 'alice'", "tags": ["private"]},
        {"title": "pwned by bob"},
        "/api/v1/snippets/search",
    ),
    "note": Resource(
        "/api/v1/notes",
        {"title": "Diary", "content": "private"},
        {"content": "pwned"},
        "/api/v1/notes",
    ),
}


@pytest.fixture(params=list(RESOURCES), ids=list(RESOURCES))
def resource(request: pytest.FixtureRequest) -> Resource:
    return RESOURCES[request.param]


async def test_another_users_row_looks_like_a_missing_row(
    api: httpx.AsyncClient, alice: Headers, bob: Headers, resource: Resource
) -> None:
    created = await api.post(resource.url, json=resource.create, headers=alice)
    alices = f"{resource.url}/{created.json()['id']}"
    missing = f"{resource.url}/{uuid.uuid4()}"

    for method, body in (("GET", None), ("PATCH", resource.change), ("DELETE", None)):
        stolen = await api.request(method, alices, json=body, headers=bob)
        absent = await api.request(method, missing, json=body, headers=bob)
        assert stolen.status_code == absent.status_code == 404, method
        assert stolen.json()["error"]["code"] == absent.json()["error"]["code"], method

    # Nothing Bob did reached Alice's row.
    unchanged = await api.get(alices, headers=alice)
    assert unchanged.status_code == 200
    for field, value in resource.create.items():
        assert unchanged.json()[field] == value


async def test_lists_only_show_your_own_rows(
    api: httpx.AsyncClient, alice: Headers, bob: Headers, resource: Resource
) -> None:
    await api.post(resource.url, json=resource.create, headers=alice)
    assert (await api.get(resource.url, headers=bob)).json()["items"] == []
    # Even when Bob searches for exactly what Alice wrote.
    query = next(iter(resource.create.values()))
    searched = await api.get(resource.search_url, params={"q": query}, headers=bob)
    assert searched.json()["items"] == []


async def test_tags_sessions_and_counts_are_per_user(
    api: httpx.AsyncClient, alice: Headers, bob: Headers
) -> None:
    for resource in RESOURCES.values():
        await api.post(resource.url, json=resource.create, headers=alice)
    await api.post("/api/v1/pomodoro/sessions", json={"duration_seconds": 1500}, headers=alice)

    assert (await api.get("/api/v1/snippets/tags", headers=bob)).json() == []
    assert (await api.get("/api/v1/pomodoro/sessions", headers=bob)).json()["items"] == []
    summary = (await api.get("/api/v1/dashboard/summary", headers=bob)).json()
    assert summary == {"snippets": 0, "notes": 0, "focus_sessions": 0, "focus_sessions_today": 0}


async def test_a_body_cannot_claim_another_owner(
    api: httpx.AsyncClient, alice: Headers, bob: Headers
) -> None:
    """Identity comes from the token only: a user_id in the body is ignored."""
    me = (await api.get("/api/v1/me", headers=alice)).json()
    created = await api.post(
        "/api/v1/notes", json={"title": "planted", "user_id": me["id"]}, headers=bob
    )
    assert created.status_code == 201
    assert (await api.get("/api/v1/notes", headers=alice)).json()["items"] == []
