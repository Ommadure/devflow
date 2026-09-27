import uuid
from collections.abc import Sequence
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Note, NoteChunk
from app.services.ai import indexing
from app.services.ai.embeddings import FakeEmbeddingProvider
from tests.helpers import RecordingDispatcher
from tests.integration.conftest import Headers

Sessions = async_sessionmaker[AsyncSession]
TWO_SECTIONS = "# Deploy\nRun the migrations.\n\n# Rollback\nRevert the tag."


class CountingProvider(FakeEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__()
        self.documents: list[str] = []

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.documents.extend(texts)
        return await super().embed_documents(texts)


async def create(api: httpx.AsyncClient, headers: Headers, **body: Any) -> uuid.UUID:
    response = await api.post("/api/v1/notes", json={"title": "Runbook", **body}, headers=headers)
    return uuid.UUID(response.json()["id"])


async def chunks(sessions: Sessions, note_id: uuid.UUID) -> list[tuple[int, str | None, str]]:
    async with sessions() as session:
        rows = await session.execute(
            select(NoteChunk.chunk_index, NoteChunk.heading, NoteChunk.content)
            .where(NoteChunk.note_id == note_id)
            .order_by(NoteChunk.chunk_index)
        )
    return [tuple(row) for row in rows]  # type: ignore[misc]


async def index(sessions: Sessions, provider: FakeEmbeddingProvider, note_id: uuid.UUID) -> str:
    async with sessions() as session:
        return await indexing.embed_note(session, provider, note_id)


async def test_saving_text_queues_indexing_but_empty_or_unchanged_saves_do_not(
    api: httpx.AsyncClient, alice: Headers, dispatcher: RecordingDispatcher
) -> None:
    empty = await create(api, alice)
    full = await create(api, alice, content="# A\ntext")
    assert dispatcher.notes == [full]

    await api.patch(f"/api/v1/notes/{full}", json={"content": "# A\ntext"}, headers=alice)
    assert dispatcher.notes == [full]  # nothing changed
    await api.patch(f"/api/v1/notes/{empty}", json={"content": "now it has text"}, headers=alice)
    assert dispatcher.notes == [full, empty]


async def test_indexing_splits_into_passages_without_touching_updated_at(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    note_id = await create(api, alice, content=TWO_SECTIONS)
    async with sessionmaker() as session:
        before = await session.scalar(select(Note.updated_at).where(Note.id == note_id))

    assert await index(sessionmaker, FakeEmbeddingProvider(), note_id) == "indexed"

    assert await chunks(sessionmaker, note_id) == [
        (0, "Deploy", "Run the migrations."),
        (1, "Rollback", "Revert the tag."),
    ]
    async with sessionmaker() as session:
        note = await session.get(Note, note_id)
    assert note is not None
    assert note.updated_at == before and note.indexed_at == before
    assert await index(sessionmaker, FakeEmbeddingProvider(), note_id) == "unchanged"


async def test_an_edit_re_embeds_only_the_passages_that_changed(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    note_id = await create(api, alice, content=TWO_SECTIONS)
    await index(sessionmaker, FakeEmbeddingProvider(), note_id)

    edited = TWO_SECTIONS.replace("Revert the tag.", "Revert the tag, then redeploy.")
    await api.patch(f"/api/v1/notes/{note_id}", json={"content": edited}, headers=alice)
    provider = CountingProvider()
    await index(sessionmaker, provider, note_id)

    assert len(provider.documents) == 1  # only "Rollback"
    assert "redeploy" in provider.documents[0]


async def test_removed_passages_are_deleted(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    note_id = await create(api, alice, content=TWO_SECTIONS)
    await index(sessionmaker, FakeEmbeddingProvider(), note_id)
    await api.patch(
        f"/api/v1/notes/{note_id}", json={"content": "# Deploy\nRun the migrations."}, headers=alice
    )
    await index(sessionmaker, FakeEmbeddingProvider(), note_id)
    assert await chunks(sessionmaker, note_id) == [(0, "Deploy", "Run the migrations.")]


async def test_an_edit_during_indexing_wins(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    note_id = await create(api, alice, content=TWO_SECTIONS)

    class EditsMeanwhile(FakeEmbeddingProvider):
        async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
            async with sessionmaker() as other:
                await other.execute(update(Note).where(Note.id == note_id).values(content="new"))
                await other.commit()
            return await super().embed_documents(texts)

    assert await index(sessionmaker, EditsMeanwhile(), note_id) == "stale"
    assert await chunks(sessionmaker, note_id) == []  # nothing written for the old text


async def test_the_sweep_indexes_notes_that_fell_behind(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    ids = [await create(api, alice, content=f"# N{i}\nbody {i}") for i in range(3)]
    async with sessionmaker() as session:
        counts = await indexing.embed_stale_notes(session, FakeEmbeddingProvider())
    assert counts["indexed"] == 3
    for note_id in ids:
        assert await chunks(sessionmaker, note_id)


async def test_deleting_a_note_deletes_its_passages(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    note_id = await create(api, alice, content=TWO_SECTIONS)
    await index(sessionmaker, FakeEmbeddingProvider(), note_id)
    await api.delete(f"/api/v1/notes/{note_id}", headers=alice)
    assert await chunks(sessionmaker, note_id) == []
    assert await index(sessionmaker, FakeEmbeddingProvider(), note_id) == "missing"
