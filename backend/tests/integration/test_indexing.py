"""The embedding pipeline: what gets queued, what the worker writes, and when it doesn't."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import undefer

from app.models import Snippet
from app.services.ai import indexing
from app.services.ai.embeddings import FakeEmbeddingProvider
from app.workers import tasks
from tests.helpers import RecordingDispatcher
from tests.integration.conftest import Headers

URL = "/api/v1/snippets"
Sessions = async_sessionmaker[AsyncSession]
BODY = {"title": "Debounce", "code": "debounce()", "tags": ["timing"]}


async def create(api: httpx.AsyncClient, headers: Headers, **overrides: Any) -> uuid.UUID:
    response = await api.post(URL, json={**BODY, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def load(sessions: Sessions, snippet_id: uuid.UUID) -> Snippet:
    async with sessions() as session:
        snippet = await session.scalar(
            select(Snippet).where(Snippet.id == snippet_id).options(undefer(Snippet.embedding))
        )
    assert snippet is not None
    return snippet


class CountingProvider(FakeEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__()
        self.documents: list[str] = []

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.documents.extend(texts)
        return await super().embed_documents(texts)


async def test_creating_a_snippet_queues_one_job(
    api: httpx.AsyncClient, alice: Headers, dispatcher: RecordingDispatcher
) -> None:
    snippet_id = await create(api, alice)
    assert dispatcher.embeds == [snippet_id]


async def test_the_job_embeds_without_touching_updated_at(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    snippet_id = await create(api, alice)
    before = await load(sessionmaker, snippet_id)

    async with sessionmaker() as session:
        assert (
            await indexing.embed_snippet(session, FakeEmbeddingProvider(), snippet_id) == "embedded"
        )

    after = await load(sessionmaker, snippet_id)
    assert after.embedding_status == "ready"
    assert after.embedding is not None and len(after.embedding) == 384
    assert after.content_hash and after.embedded_at
    assert after.updated_at == before.updated_at  # embedding isn't an edit


async def test_running_the_job_twice_is_free(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    snippet_id = await create(api, alice)
    provider = CountingProvider()
    async with sessionmaker() as session:
        await indexing.embed_snippet(session, provider, snippet_id)
    async with sessionmaker() as session:
        assert await indexing.embed_snippet(session, provider, snippet_id) == "unchanged"
    assert len(provider.documents) == 1


async def test_only_text_changes_re_embed(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions, dispatcher: RecordingDispatcher
) -> None:
    snippet_id = await create(api, alice)
    async with sessionmaker() as session:
        await indexing.embed_snippet(session, FakeEmbeddingProvider(), snippet_id)
    one = f"{URL}/{snippet_id}"

    starred = await api.patch(one, json={"favorite": True}, headers=alice)
    assert starred.json()["embedding_status"] == "ready"
    assert dispatcher.embeds == [snippet_id]  # no new job

    edited = await api.patch(one, json={"code": "debounce(fn, 300)"}, headers=alice)
    assert edited.json()["embedding_status"] == "pending"
    assert dispatcher.embeds == [snippet_id, snippet_id]


async def test_a_job_never_overwrites_a_newer_edit(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    """The user edits while the worker is embedding the old text: the old vector is dropped
    (the edit queued its own job) instead of being stored against the new text."""
    snippet_id = await create(api, alice)

    class EditsDuringEmbedding(FakeEmbeddingProvider):
        async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
            async with sessionmaker() as other:
                await other.execute(
                    update(Snippet).where(Snippet.id == snippet_id).values(code="edited meanwhile")
                )
                await other.commit()
            return await super().embed_documents(texts)

    async with sessionmaker() as session:
        outcome = await indexing.embed_snippet(session, EditsDuringEmbedding(), snippet_id)
    assert outcome == "stale"
    snippet = await load(sessionmaker, snippet_id)
    assert (snippet.embedding_status, snippet.embedding) == ("pending", None)


async def test_a_deleted_snippet_is_skipped(sessionmaker: Sessions, migrated_database: str) -> None:
    async with sessionmaker() as session:
        assert (
            await indexing.embed_snippet(session, FakeEmbeddingProvider(), uuid.uuid4())
            == "missing"
        )


async def test_backfill_embeds_pending_in_batches_and_failed_on_request(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    ids = [await create(api, alice, title=f"Snippet {n}") for n in range(5)]
    async with sessionmaker() as session:
        await indexing.mark_failed(session, ids[0])

    provider = CountingProvider()
    async with sessionmaker() as session:
        counts = await indexing.embed_pending(session, provider, batch_size=2)
    assert counts["embedded"] == 4
    assert (await load(sessionmaker, ids[0])).embedding_status == "failed"

    async with sessionmaker() as session:
        counts = await indexing.embed_pending(session, provider, include_failed=True)
    assert counts["embedded"] == 1
    assert {(await load(sessionmaker, i)).embedding_status for i in ids} == {"ready"}


async def test_the_sweep_leaves_recent_rows_to_their_own_jobs(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    recent = await create(api, alice)
    lost = await create(api, alice, title="Lost job")
    async with sessionmaker() as session:
        await session.execute(
            update(Snippet)
            .where(Snippet.id == lost)
            .values(updated_at=datetime.now(UTC) - timedelta(minutes=30))
        )
        await session.commit()
        await indexing.embed_pending(
            session, FakeEmbeddingProvider(), older_than=indexing.sweep_cutoff(datetime.now(UTC))
        )
    assert (await load(sessionmaker, lost)).embedding_status == "ready"
    assert (await load(sessionmaker, recent)).embedding_status == "pending"


async def test_the_task_retries_then_marks_failed(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    snippet_id = await create(api, alice)
    attempts: list[int] = []

    async def broken(*_: object) -> None:
        attempts.append(1)
        raise RuntimeError("model crashed")

    monkeypatch.setattr(indexing, "embed_snippet", broken)  # the module tasks call into
    monkeypatch.setattr(tasks, "backoff_seconds", lambda _attempt: 0)
    await tasks.embed_snippet_task(str(snippet_id))

    assert len(attempts) == tasks.MAX_ATTEMPTS
    assert (await load(sessionmaker, snippet_id)).embedding_status == "failed"
