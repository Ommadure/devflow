"""Semantic search must find a user's own rows however many *other* users' vectors sit
closer to the query in the shared HNSW index (app/repositories/_vector.py).

Found by the Phase 7 evaluation work: pgvector filters after the index scan, so once the
planner uses HNSW, the 40 candidates it returns can all belong to someone else.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Note, NoteChunk, Snippet, User
from app.repositories.note_search import search_chunks
from app.repositories.search import Filters, hybrid_search
from app.services.ai.embeddings import FakeEmbeddingProvider

Sessions = async_sessionmaker[AsyncSession]
# Production: over 40 (hnsw.ef_search) other users' vectors nearer the query than mine.
# Here the same thing in miniature, ef_search 10 and 20 of theirs. 23 rows in all is under
# the 32 links each HNSW node keeps, so the graph is complete: every row is reachable, and
# only the scan's stopping rule decides what comes back.
CROWD, EF_SEARCH = 20, 10


MINE = ["alpha alpha beta", "alpha alpha delta", "alpha beta"]  # distance ≈ 0.11, 0.11, 0.29


def vectors(embeddings: FakeEmbeddingProvider) -> tuple[list[float], list[str]]:
    """The query, and the crowd's texts: each ≈ 0.05 from it, nearer than any of mine."""
    return embeddings.vector("alpha"), [f"alpha alpha alpha crowd{i}" for i in range(CROWD)]


async def users(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    me, crowd = uuid.uuid4(), uuid.uuid4()
    session.add_all(
        [
            User(id=me, email="me@example.com", password_hash="!"),
            User(id=crowd, email="crowd@example.com", password_hash="!"),
        ]
    )
    await session.flush()
    return me, crowd


async def force_hnsw(session: AsyncSession, table: str, user_index: str, me: uuid.UUID) -> None:
    """Put this transaction (rolled back at the end) in production's shoes:

    - drop the user_id index, which a table this small would rather use;
    - rebuild the HNSW index, so it holds only this test's rows (the suite cleans up with
      DELETE, which leaves dead entries in the graph until a VACUUM);
    - shrink ef_search to match the miniature crowd.
    """
    await session.execute(text(f"DROP INDEX {user_index}"))
    await session.execute(text(f"REINDEX INDEX ix_{table}_embedding_hnsw"))
    await session.execute(text("SET LOCAL enable_seqscan = off"))
    await session.execute(text(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}"))
    plan = await session.scalars(
        text(
            f"EXPLAIN SELECT id FROM {table} WHERE user_id = :me "  # noqa: S608 (constants)
            "ORDER BY embedding <=> CAST(:q AS vector) LIMIT 20"
        ),
        {"me": me, "q": str([1.0] + [0.0] * 383)},
    )
    assert f"ix_{table}_embedding_hnsw" in "\n".join(plan)  # HNSW really serves it


def snippet(user_id: uuid.UUID, title: str, vector: list[float]) -> Snippet:
    return Snippet(
        user_id=user_id, title=title, code="-", embedding=vector, embedding_status="ready"
    )


async def test_snippet_search_sees_past_other_users_vectors(
    sessionmaker: Sessions, embeddings: FakeEmbeddingProvider
) -> None:
    query, crowd_texts = vectors(embeddings)
    async with sessionmaker() as session:
        me, crowd = await users(session)
        session.add_all(snippet(me, t, embeddings.vector(t)) for t in MINE)
        session.add_all(snippet(crowd, t, embeddings.vector(t)) for t in crowd_texts)
        await session.commit()

    async with sessionmaker() as session:
        await force_hnsw(session, "snippets", "ix_snippets_user_id_created_at_id", me)
        hits = await hybrid_search(
            session,
            me,
            q="zzz",
            vector=query,
            mode="semantic",
            filters=Filters(),
            max_distance=0.4,
            limit=10,
        )
    assert sorted(hit.snippet.title for hit in hits) == sorted(MINE)


async def test_note_retrieval_sees_past_other_users_vectors(
    sessionmaker: Sessions, embeddings: FakeEmbeddingProvider
) -> None:
    query, crowd_texts = vectors(embeddings)
    async with sessionmaker() as session:
        me, crowd = await users(session)
        my_note, their_note = Note(user_id=me, title="Mine"), Note(user_id=crowd, title="Theirs")
        session.add_all([my_note, their_note])
        await session.flush()

        def chunk(note: Note, index: int, content: str, vector: list[float]) -> NoteChunk:
            return NoteChunk(
                note_id=note.id,
                user_id=note.user_id,
                chunk_index=index,
                content=content,
                content_hash="-",
                token_count=1,
                embedding=vector,
            )

        session.add_all(chunk(my_note, i, t, embeddings.vector(t)) for i, t in enumerate(MINE))
        session.add_all(
            chunk(their_note, i, t, embeddings.vector(t)) for i, t in enumerate(crowd_texts)
        )
        await session.commit()

    async with sessionmaker() as session:
        await force_hnsw(session, "note_chunks", "ix_note_chunks_user_id", me)
        hits = await search_chunks(session, me, q="zzz", vector=query, max_distance=0.4, limit=6)
    assert sorted(hit.chunk.content for hit in hits) == sorted(MINE)
