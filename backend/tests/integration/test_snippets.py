from typing import Any

import httpx

from tests.integration.conftest import Headers

URL = "/api/v1/snippets"
DEBOUNCE = {
    "title": "Debounce",
    "description": "Delay a call until input settles",
    "code": (
        "function debounce(fn, ms) {\n"
        "  let t;\n"
        "  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };\n"
        "}"
    ),
    "language": "JavaScript",
    "tags": ["Timing", "react hooks"],
}


async def create(api: httpx.AsyncClient, headers: Headers, **overrides: object) -> dict[str, Any]:
    response = await api.post(URL, json={**DEBOUNCE, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_create_normalises_and_returns_the_snippet(
    api: httpx.AsyncClient, alice: Headers
) -> None:
    snippet = await create(api, alice)
    assert snippet["language"] == "javascript"
    assert snippet["tags"] == ["timing", "react-hooks"]
    assert snippet["favorite"] is False
    assert snippet["created_at"] == snippet["updated_at"]


async def test_get_update_delete(api: httpx.AsyncClient, alice: Headers) -> None:
    snippet = await create(api, alice)
    one = f"{URL}/{snippet['id']}"

    assert (await api.get(one, headers=alice)).json()["title"] == "Debounce"

    updated = await api.patch(one, json={"favorite": True, "language": None}, headers=alice)
    assert updated.status_code == 200
    body = updated.json()
    assert (body["favorite"], body["language"], body["title"]) == (True, None, "Debounce")
    assert body["updated_at"] > body["created_at"]

    assert (await api.delete(one, headers=alice)).status_code == 204
    missing = await api.get(one, headers=alice)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SNIPPET_NOT_FOUND"


async def test_required_fields_cannot_be_nulled(api: httpx.AsyncClient, alice: Headers) -> None:
    snippet = await create(api, alice)
    response = await api.patch(f"{URL}/{snippet['id']}", json={"title": None}, headers=alice)
    assert response.status_code == 422


async def test_invalid_input_is_rejected(api: httpx.AsyncClient, alice: Headers) -> None:
    blank_title = await api.post(URL, json={**DEBOUNCE, "title": "   "}, headers=alice)
    too_many_tags = await api.post(
        URL, json={**DEBOUNCE, "tags": [f"t{i}" for i in range(21)]}, headers=alice
    )
    assert blank_title.status_code == too_many_tags.status_code == 422


async def test_every_route_requires_a_token(api: httpx.AsyncClient) -> None:
    assert (await api.get(URL)).status_code == 401
    assert (await api.post(URL, json=DEBOUNCE)).status_code == 401


async def test_filters(api: httpx.AsyncClient, alice: Headers) -> None:
    await create(api, alice, title="Debounce", tags=["timing"], favorite=True)
    await create(api, alice, title="Throttle", code="throttle()", language="TypeScript", tags=[])
    await create(api, alice, title="100% width", code="width: 100%;", language="css", tags=[])

    async def titles(**params: str) -> list[str]:
        response = await api.get(URL, params=params, headers=alice)
        return sorted(item["title"] for item in response.json()["items"])

    assert await titles(q="throt") == ["Throttle"]
    assert await titles(language="TYPESCRIPT") == ["Throttle"]
    assert await titles(tag="timing") == ["Debounce"]
    assert await titles(favorite="true") == ["Debounce"]
    # % is matched literally, not as "anything".
    assert await titles(q="100%") == ["100% width"]
    assert await titles(q="%") == ["100% width"]


async def test_cursor_pagination_walks_every_row_once(
    api: httpx.AsyncClient, alice: Headers
) -> None:
    created = [(await create(api, alice, title=f"Snippet {n}"))["id"] for n in range(7)]
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": "3", **({"cursor": cursor} if cursor else {})}
        body = (await api.get(URL, params=params, headers=alice)).json()
        seen += [item["id"] for item in body["items"]]
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert pages == 3
    assert seen == list(reversed(created))  # newest first, nothing skipped or repeated


async def test_bad_cursor_and_limit_are_422(api: httpx.AsyncClient, alice: Headers) -> None:
    bad_cursor = await api.get(URL, params={"cursor": "not-a-cursor"}, headers=alice)
    assert bad_cursor.status_code == 422
    assert bad_cursor.json()["error"]["code"] == "INVALID_CURSOR"
    assert (await api.get(URL, params={"limit": "101"}, headers=alice)).status_code == 422


async def test_tag_counts(api: httpx.AsyncClient, alice: Headers) -> None:
    await create(api, alice, tags=["react", "timing"])
    await create(api, alice, tags=["react"])
    response = await api.get(f"{URL}/tags", headers=alice)
    assert response.json() == [{"tag": "react", "count": 2}, {"tag": "timing", "count": 1}]
