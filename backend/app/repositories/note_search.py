"""Retrieval for "ask your notes": hybrid search over one user's note passages.

Same shape as snippet search (keyword + semantic, fused with RRF), plus the semantic
similarity of each hit — the guardrail uses it to answer "not found" without an LLM call.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Note, NoteChunk
from app.repositories._rrf import fuse
from app.repositories._vector import scan_past_other_users

BRANCH_LIMIT = 20


@dataclass(frozen=True)
class ChunkHit:
    chunk: NoteChunk
    note_title: str
    score: float
    similarity: float | None  # None when only the keyword branch found it


async def search_chunks(
    session: AsyncSession,
    user_id: UUID,
    *,
    q: str,
    vector: list[float],
    max_distance: float,
    limit: int,
) -> list[ChunkHit]:
    tsquery = func.websearch_to_tsquery(literal_column("'english'::regconfig"), q)
    rank = func.ts_rank_cd(NoteChunk.search_tsv, tsquery)
    keyword_top = (
        select(NoteChunk.id.label("id"), rank.label("relevance"))
        .where(NoteChunk.user_id == user_id, NoteChunk.search_tsv.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(BRANCH_LIMIT)
        .subquery()
    )
    keyword = select(
        keyword_top.c.id,
        func.row_number()
        .over(order_by=(keyword_top.c.relevance.desc(), keyword_top.c.id))
        .label("rank"),
    ).cte("keyword")

    distance = NoteChunk.embedding.cosine_distance(vector)
    semantic_top = (
        select(NoteChunk.id.label("id"), distance.label("distance"))
        .where(NoteChunk.user_id == user_id, distance <= max_distance)
        .order_by(distance)  # the distance alone, so the HNSW index can serve it
        .limit(BRANCH_LIMIT)
        .subquery()
    )
    semantic = select(
        semantic_top.c.id,
        semantic_top.c.distance,
        func.row_number().over(order_by=(semantic_top.c.distance, semantic_top.c.id)).label("rank"),
    ).cte("semantic")

    fused = fuse(keyword, semantic)
    if fused is None:  # unreachable: both branches are always present here
        return []
    await scan_past_other_users(session)
    rows = await session.execute(
        select(NoteChunk, Note.title, fused.c.score, semantic.c.distance)
        .join(fused, NoteChunk.id == fused.c.id)
        .join(Note, Note.id == NoteChunk.note_id)
        .outerjoin(semantic, semantic.c.id == NoteChunk.id)
        .where(NoteChunk.user_id == user_id)
        .order_by(fused.c.score.desc(), NoteChunk.id)
        .limit(limit)
    )
    return [
        ChunkHit(
            chunk=chunk,
            note_title=title,
            score=float(score),
            similarity=None if dist is None else 1 - float(dist),
        )
        for chunk, title, score, dist in rows
    ]
