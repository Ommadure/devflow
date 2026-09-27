"""Hybrid search against real Postgres (tsvector + pgvector) with deterministic fake vectors.

The fake model is a bag of words, so texts sharing words are similar. `embeddings.aliases`
makes a query embed exactly like a given snippet — a match with no words in common, i.e.
one only semantic search can find.
"""

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Snippet
from app.repositories.search import RRF_K
from app.services.ai import indexing
from app.services.ai.embedding_text import embedding_text
from app.services.ai.embeddings import FakeEmbeddingProvider
from tests.integration.conftest import Headers

URL = "/api/v1/snippets"
SEARCH = f"{URL}/search"
Sessions = async_sessionmaker[AsyncSession]

DEBOUNCE = {
    "title": "Timing helper",
    "description": "Wait until input settles",
    "code": (
        "function debounce(fn, ms) {\n"
        "  let t;\n"
        "  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };\n"
        "}"
    ),
    "language": "javascript",
    "tags": ["timing"],
}
UPSERT = {
    "title": "Upsert a row",
    "code": (
        "INSERT INTO users (id, email) VALUES ($1, $2)\n"
        "ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email;"
    ),
    "language": "sql",
}
INTENT = "stop a function from firing too often"  # shares no word with DEBOUNCE


async def create(api: httpx.AsyncClient, headers: Headers, body: dict[str, Any]) -> str:
    response = await api.post(URL, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def index_all(sessions: Sessions, embeddings: FakeEmbeddingProvider) -> None:
    async with sessions() as session:
        await indexing.embed_pending(session, embeddings)


async def alias_to(
    sessions: Sessions, embeddings: FakeEmbeddingProvider, query: str, snippet_id: str
) -> None:
    """Make `query` embed exactly like the snippet: a perfect semantic match."""
    async with sessions() as session:
        snippet = await session.scalar(select(Snippet).where(Snippet.id == snippet_id))
        assert snippet is not None
        embeddings.aliases[query] = embedding_text(snippet)


async def search(
    api: httpx.AsyncClient, headers: Headers, q: str, **params: str
) -> list[dict[str, Any]]:
    response = await api.get(SEARCH, params={"q": q, **params}, headers=headers)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def test_intent_query_finds_what_keywords_miss(
    api: httpx.AsyncClient,
    alice: Headers,
    sessionmaker: Sessions,
    embeddings: FakeEmbeddingProvider,
) -> None:
    """The Phase 4 exit criterion, in miniature."""
    debounce = await create(api, alice, DEBOUNCE)
    await create(api, alice, UPSERT)
    await index_all(sessionmaker, embeddings)
    await alias_to(sessionmaker, embeddings, INTENT, debounce)

    assert await search(api, alice, INTENT, mode="keyword") == []
    [hit] = await search(api, alice, INTENT, mode="hybrid")
    assert (hit["id"], hit["match_type"]) == (debounce, "semantic")


async def test_keyword_search_works_before_embedding(
    api: httpx.AsyncClient, alice: Headers
) -> None:
    debounce = await create(api, alice, DEBOUNCE)  # still "pending": no vector yet
    [hit] = await search(api, alice, "debounce")
    assert (hit["id"], hit["match_type"], hit["embedding_status"]) == (
        debounce,
        "keyword",
        "pending",
    )


async def test_prose_is_stemmed_code_is_exact_and_titles_weigh_most(
    api: httpx.AsyncClient, alice: Headers
) -> None:
    in_title = await create(api, alice, {**UPSERT, "title": "Settling promises"})
    in_code = await create(api, alice, {**UPSERT, "code": "await settle(promise);"})
    in_code_inflected = await create(api, alice, {**UPSERT, "code": "promise.settles();"})

    hits = [hit["id"] for hit in await search(api, alice, "settle", mode="keyword")]
    # Prose is stemmed ("Settling" matches "settle"); code keeps identifiers exact, so
    # `settle(` matches and `settles(` doesn't. A title hit (weight A) outranks code (C).
    assert hits == [in_title, in_code]
    assert in_code_inflected not in hits


async def test_rrf_rewards_agreement_between_branches(
    api: httpx.AsyncClient,
    alice: Headers,
    sessionmaker: Sessions,
    embeddings: FakeEmbeddingProvider,
) -> None:
    # B has "debounce" in its title: keyword rank 1. A only in its code: keyword rank 2 —
    # but A is also the semantic match. Fused, A wins: 1/62 + 1/61 > 1/61.
    b = await create(api, alice, {**UPSERT, "title": "Debounce notes", "code": "see docs"})
    a = await create(api, alice, DEBOUNCE)
    await index_all(sessionmaker, embeddings)
    await alias_to(sessionmaker, embeddings, "debounce", a)

    hits = await search(api, alice, "debounce")
    assert [(h["id"], h["match_type"]) for h in hits] == [(a, "both"), (b, "keyword")]
    assert hits[0]["score"] == round(1 / (RRF_K + 2) + 1 / (RRF_K + 1), 6)
    assert hits[1]["score"] == round(1 / (RRF_K + 1), 6)


async def test_modes_return_one_branch(
    api: httpx.AsyncClient,
    alice: Headers,
    sessionmaker: Sessions,
    embeddings: FakeEmbeddingProvider,
) -> None:
    a = await create(api, alice, DEBOUNCE)
    await index_all(sessionmaker, embeddings)
    await alias_to(sessionmaker, embeddings, "debounce", a)

    [keyword] = await search(api, alice, "debounce", mode="keyword")
    [semantic] = await search(api, alice, "debounce", mode="semantic")
    assert (keyword["match_type"], semantic["match_type"]) == ("keyword", "semantic")


async def test_unrelated_queries_match_nothing(
    api: httpx.AsyncClient,
    alice: Headers,
    sessionmaker: Sessions,
    embeddings: FakeEmbeddingProvider,
) -> None:
    # Nearest neighbours always exist; the similarity cut-off stops them posing as matches.
    await create(api, alice, DEBOUNCE)
    await index_all(sessionmaker, embeddings)
    assert await search(api, alice, "quarterly tax return", mode="semantic") == []


async def test_filters_apply_to_both_branches(
    api: httpx.AsyncClient,
    alice: Headers,
    sessionmaker: Sessions,
    embeddings: FakeEmbeddingProvider,
) -> None:
    js = await create(api, alice, DEBOUNCE)
    await create(api, alice, {**DEBOUNCE, "language": "python", "tags": ["other"]})
    await index_all(sessionmaker, embeddings)

    assert [h["id"] for h in await search(api, alice, "debounce", language="JavaScript")] == [js]
    assert [h["id"] for h in await search(api, alice, "debounce", tag="timing")] == [js]
    assert await search(api, alice, "debounce", favorite="true") == []


async def test_search_is_per_user(
    api: httpx.AsyncClient,
    alice: Headers,
    bob: Headers,
    sessionmaker: Sessions,
    embeddings: FakeEmbeddingProvider,
) -> None:
    a = await create(api, alice, DEBOUNCE)
    await index_all(sessionmaker, embeddings)
    await alias_to(sessionmaker, embeddings, INTENT, a)
    for mode in ("keyword", "semantic", "hybrid"):
        assert await search(api, bob, "debounce", mode=mode) == []
        assert await search(api, bob, INTENT, mode=mode) == []


async def test_query_syntax_and_odd_characters_are_safe(
    api: httpx.AsyncClient, alice: Headers
) -> None:
    await create(api, alice, DEBOUNCE)
    for q in [
        '"input settles" -python',
        "it's 100% _weird_ \\ ; drop table snippets",
        "or",
        "&&!!",
    ]:
        response = await api.get(SEARCH, params={"q": q}, headers=alice)
        assert response.status_code == 200, (q, response.text)


async def test_bad_parameters_are_422(api: httpx.AsyncClient, alice: Headers) -> None:
    assert (await api.get(SEARCH, params={"q": ""}, headers=alice)).status_code == 422
    assert (
        await api.get(SEARCH, params={"q": "x", "mode": "magic"}, headers=alice)
    ).status_code == 422
    assert (
        await api.get(SEARCH, params={"q": "x", "limit": "51"}, headers=alice)
    ).status_code == 422


async def test_query_embeddings_are_cached(
    api: httpx.AsyncClient, alice: Headers, embeddings: FakeEmbeddingProvider
) -> None:
    calls: list[str] = []
    original = embeddings.embed_query

    async def counting(text: str) -> list[float]:
        calls.append(text)
        return await original(text)

    embeddings.embed_query = counting  # type: ignore[method-assign]
    await search(api, alice, "debounce")
    await search(api, alice, "debounce", mode="semantic")
    assert calls == ["debounce"]


async def test_words_inside_camel_case_identifiers_are_found(
    api: httpx.AsyncClient, alice: Headers
) -> None:
    in_title = await create(api, alice, {**UPSERT, "title": "useDebounce"})
    in_code = await create(
        api, alice, {**UPSERT, "code": "const user = await fetchUserProfile(id);"}
    )

    assert [h["id"] for h in await search(api, alice, "debounce", mode="keyword")] == [in_title]
    assert [h["id"] for h in await search(api, alice, "profile", mode="keyword")] == [in_code]
    # The whole identifier still matches as typed.
    assert [h["id"] for h in await search(api, alice, "useDebounce", mode="keyword")] == [in_title]
