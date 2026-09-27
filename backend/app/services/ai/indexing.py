"""Embedding jobs: the work the Taskiq worker does, as plain functions (easy to test).

These run as the system, not as a user, so they look snippets up by id alone. That is the
one sanctioned exception to "every query filters by user_id" — nothing here is reachable
from an HTTP request, and nothing is returned to anyone.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import structlog
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Note, NoteChunk, Snippet
from app.services.ai.chunking import chunk_embedding_text, chunk_note
from app.services.ai.embedding_text import content_hash, embedding_text
from app.services.ai.embeddings import EmbeddingProvider

log = structlog.get_logger()

Outcome = Literal["embedded", "unchanged", "missing", "stale"]
BATCH_SIZE = 32


async def embed_snippet(
    session: AsyncSession, provider: EmbeddingProvider, snippet_id: uuid.UUID
) -> Outcome:
    snippet = await session.get(Snippet, snippet_id)
    if snippet is None:
        return "missing"  # deleted before the job ran
    [outcome] = await _embed(session, provider, [snippet])
    return outcome


async def embed_pending(
    session: AsyncSession,
    provider: EmbeddingProvider,
    *,
    include_failed: bool = False,
    older_than: datetime | None = None,
    batch_size: int = BATCH_SIZE,
) -> dict[Outcome, int]:
    """Embed every snippet that isn't ready, `batch_size` at a time (the backfill).

    `older_than` limits it to rows untouched since then — the scheduled sweep uses it to
    pick up only jobs that were lost, not ones still sitting in the queue.
    """
    counts: dict[Outcome, int] = {"embedded": 0, "unchanged": 0, "missing": 0, "stale": 0}
    statuses = ["pending", "failed"] if include_failed else ["pending"]
    seen: set[uuid.UUID] = set()
    while True:
        stmt = (
            select(Snippet)
            .where(Snippet.embedding_status.in_(statuses))
            .order_by(Snippet.created_at)
            .limit(batch_size)
        )
        if seen:
            stmt = stmt.where(Snippet.id.not_in(seen))
        if older_than is not None:
            stmt = stmt.where(Snippet.updated_at < older_than)
        batch = list(await session.scalars(stmt))
        if not batch:
            return counts
        seen.update(snippet.id for snippet in batch)  # never loop forever on a stuck row
        for outcome in await _embed(session, provider, batch):
            counts[outcome] += 1


async def mark_failed(session: AsyncSession, snippet_id: uuid.UUID) -> None:
    await session.execute(
        update(Snippet)
        .where(Snippet.id == snippet_id)
        # updated_at is set to itself: an embedding status change isn't an edit.
        .values(embedding_status="failed", updated_at=Snippet.updated_at)
    )
    await session.commit()


def sweep_cutoff(now: datetime, grace: timedelta = timedelta(minutes=5)) -> datetime:
    return now - grace


@dataclass(frozen=True)
class _Work:
    snippet: Snippet
    text: str
    hash: str


async def _embed(
    session: AsyncSession, provider: EmbeddingProvider, snippets: list[Snippet]
) -> list[Outcome]:
    work = []
    outcomes: dict[uuid.UUID, Outcome] = {}
    for snippet in snippets:
        text = embedding_text(snippet)
        digest = content_hash(text, provider.model_name)
        if snippet.embedding_status == "ready" and snippet.content_hash == digest:
            outcomes[snippet.id] = "unchanged"  # idempotency: a repeated job costs nothing
        else:
            work.append(_Work(snippet, text, digest))

    if work:
        vectors = await provider.embed_documents([item.text for item in work])
        for item, vector in zip(work, vectors, strict=True):
            # Optimistic concurrency: write only if the row is still the version we read.
            # If the user edited it meanwhile, a newer job embeds the newer text; writing
            # ours would store a vector for text that no longer exists.
            result = await session.execute(
                update(Snippet)
                .where(Snippet.id == item.snippet.id, Snippet.updated_at == item.snippet.updated_at)
                .values(
                    embedding=vector,
                    content_hash=item.hash,
                    embedding_status="ready",
                    embedded_at=func.now(),
                    updated_at=Snippet.updated_at,  # not an edit: keep the list order
                )
            )
            outcomes[item.snippet.id] = "embedded" if result.rowcount else "stale"  # type: ignore[attr-defined]
        await session.commit()

    for snippet_id, outcome in outcomes.items():
        log.info("embedding.done", snippet_id=str(snippet_id), outcome=outcome)
    return [outcomes[snippet.id] for snippet in snippets]


# ---- notes: chunk, then embed only the passages that changed (spec §11.5) ----

NoteOutcome = Literal["indexed", "unchanged", "missing", "stale"]


async def embed_note(
    session: AsyncSession, provider: EmbeddingProvider, note_id: uuid.UUID
) -> NoteOutcome:
    note = await session.get(Note, note_id)
    if note is None:
        return "missing"  # deleted; its chunks went with it (ON DELETE CASCADE)
    version = note.updated_at
    if note.indexed_at == version:
        return "unchanged"

    chunks = chunk_note(note.content)
    wanted = [
        (chunk, content_hash(chunk_embedding_text(note.title, chunk), provider.model_name))
        for chunk in chunks
    ]
    existing = {
        row.chunk_index: row.content_hash
        for row in await session.execute(
            select(NoteChunk.chunk_index, NoteChunk.content_hash).where(
                NoteChunk.note_id == note.id
            )
        )
    }
    # Autosave fires every second while typing; a typical edit changes one passage.
    changed = [(chunk, digest) for chunk, digest in wanted if existing.get(chunk.index) != digest]
    vectors = (
        await provider.embed_documents(
            [chunk_embedding_text(note.title, chunk) for chunk, _ in changed]
        )
        if changed
        else []
    )

    # Lock the note and re-check its version before writing: if it was edited while we
    # were embedding, these passages describe text that no longer exists. The edit queued
    # its own job, so drop ours.
    current = await session.scalar(
        select(Note.updated_at).where(Note.id == note.id).with_for_update()
    )
    if current != version:
        await session.rollback()
        return "stale"

    for (chunk, digest), vector in zip(changed, vectors, strict=True):
        values = {
            "heading": chunk.heading,
            "content": chunk.content,
            "content_hash": digest,
            "token_count": chunk.token_count,
            "embedding": vector,
        }
        await session.execute(
            pg_insert(NoteChunk)
            .values(note_id=note.id, user_id=note.user_id, chunk_index=chunk.index, **values)
            .on_conflict_do_update(index_elements=["note_id", "chunk_index"], set_=values)
        )
    await session.execute(
        delete(NoteChunk).where(NoteChunk.note_id == note.id, NoteChunk.chunk_index >= len(chunks))
    )
    await session.execute(
        update(Note)
        .where(Note.id == note.id)
        .values(indexed_at=version, updated_at=Note.updated_at)  # indexing isn't an edit
    )
    await session.commit()
    log.info("note.indexed", note_id=str(note.id), passages=len(chunks), embedded=len(changed))
    return "indexed"


async def embed_stale_notes(
    session: AsyncSession, provider: EmbeddingProvider, *, older_than: datetime | None = None
) -> dict[NoteOutcome, int]:
    """Re-index every note whose passages are behind its text (the backfill and the sweep)."""
    stmt = select(Note.id).where(or_(Note.indexed_at.is_(None), Note.indexed_at < Note.updated_at))
    if older_than is not None:
        stmt = stmt.where(Note.updated_at < older_than)
    counts: dict[NoteOutcome, int] = {"indexed": 0, "unchanged": 0, "missing": 0, "stale": 0}
    for note_id in list(await session.scalars(stmt)):
        counts[await embed_note(session, provider, note_id)] += 1
    return counts
