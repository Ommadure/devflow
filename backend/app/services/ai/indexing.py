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
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Snippet
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
