from typing import Any

import httpx

from tests.integration.conftest import Headers

URL = "/api/v1/notes"


async def create(api: httpx.AsyncClient, headers: Headers, **body: str) -> dict[str, Any]:
    response = await api.post(URL, json=body, headers=headers)
    assert response.status_code == 201, response.text
    note: dict[str, Any] = response.json()
    return note


async def test_a_new_note_can_start_empty(api: httpx.AsyncClient, alice: Headers) -> None:
    note = await create(api, alice)
    assert (note["title"], note["content"]) == ("", "")


async def test_get_update_delete(api: httpx.AsyncClient, alice: Headers) -> None:
    note = await create(api, alice, title="Plan", content="# Phase 3")
    one = f"{URL}/{note['id']}"

    updated = (await api.patch(one, json={"content": "# Phase 3\n- notes"}, headers=alice)).json()
    assert (updated["title"], updated["content"]) == ("Plan", "# Phase 3\n- notes")

    assert (await api.delete(one, headers=alice)).status_code == 204
    missing = await api.get(one, headers=alice)
    assert missing.json()["error"]["code"] == "NOTE_NOT_FOUND"


async def test_list_is_sorted_by_last_update(api: httpx.AsyncClient, alice: Headers) -> None:
    first = await create(api, alice, title="First")
    await create(api, alice, title="Second")
    await api.patch(f"{URL}/{first['id']}", json={"content": "edited"}, headers=alice)

    items = (await api.get(URL, headers=alice)).json()["items"]
    assert [item["title"] for item in items] == ["First", "Second"]


async def test_search(api: httpx.AsyncClient, alice: Headers) -> None:
    await create(api, alice, title="Groceries", content="milk")
    await create(api, alice, title="Standup", content="blocked on snake_case bug")

    async def titles(q: str) -> list[str]:
        items = (await api.get(URL, params={"q": q}, headers=alice)).json()["items"]
        return [item["title"] for item in items]

    assert await titles("MILK") == ["Groceries"]
    assert await titles("snake_case") == ["Standup"]
    assert await titles("snake%case") == []  # wildcards are literal


async def test_null_fields_are_rejected(api: httpx.AsyncClient, alice: Headers) -> None:
    note = await create(api, alice)
    response = await api.patch(f"{URL}/{note['id']}", json={"content": None}, headers=alice)
    assert response.status_code == 422
