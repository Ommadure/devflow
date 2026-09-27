"""Hybrid snippet search: full-text and vector search fused with Reciprocal Rank Fusion.

One SQL statement, three CTEs, always scoped to one user (ADR 0005):

1. keyword  — the user's snippets matching `websearch_to_tsquery`, best `ts_rank_cd` first.
2. semantic — the user's embedded snippets nearest the query vector (cosine distance).
3. fused    — score = Σ 1 / (60 + rank) over the branches a snippet appears in.

Why ranks and not scores: ts_rank_cd is an unbounded weighted count, cosine distance runs
0..2 — adding them is adding metres to kilograms, and any fixed weighting between them
breaks as soon as the data changes. Ranks are on the same scale in every branch. The
constant 60 (from the RRF paper) keeps one first place from swamping several strong
second places; a snippet both branches like rises to the top.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Snippet
from app.repositories._rrf import RRF_K, fuse

Mode = Literal["keyword", "semantic", "hybrid"]
MatchType = Literal["keyword", "semantic", "both"]

BRANCH_LIMIT = 50


@dataclass(frozen=True)
class Filters:
    language: str | None = None
    tag: str | None = None
    favorite: bool | None = None


@dataclass(frozen=True)
class Hit:
    snippet: Snippet
    score: float
    match_type: MatchType


def _owned(user_id: UUID, filters: Filters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [Snippet.user_id == user_id]
    if filters.language:
        conditions.append(Snippet.language == filters.language)
    if filters.tag:
        conditions.append(Snippet.tags.contains([filters.tag]))
    if filters.favorite is not None:
        conditions.append(Snippet.favorite.is_(filters.favorite))
    return conditions


def _keyword_branch(q: str, conditions: list[ColumnElement[bool]]) -> Select[tuple[UUID, int]]:
    # The query is parsed twice and OR-ed: 'english' stems prose ("debouncing" → "debounc"),
    # 'simple' keeps identifiers as typed, matching how search_tsv indexed each part.
    tsquery = func.websearch_to_tsquery(literal_column("'english'::regconfig"), q).op("||")(
        func.websearch_to_tsquery(literal_column("'simple'::regconfig"), q)
    )
    rank = func.ts_rank_cd(Snippet.search_tsv, tsquery)
    top = (
        select(Snippet.id.label("id"), rank.label("relevance"))
        .where(*conditions, Snippet.search_tsv.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(BRANCH_LIMIT)
        .subquery()
    )
    return select(
        top.c.id,
        func.row_number().over(order_by=(top.c.relevance.desc(), top.c.id)).label("rank"),
    )


def _semantic_branch(
    vector: list[float], max_distance: float, conditions: list[ColumnElement[bool]]
) -> Select[tuple[UUID, int]]:
    distance = Snippet.embedding.cosine_distance(vector)
    top = (
        select(Snippet.id.label("id"), distance.label("distance"))
        .where(
            *conditions,
            Snippet.embedding_status == "ready",
            # Nearest neighbours always exist; without a cut-off, a query about anything
            # would "match" every snippet. Only reasonably similar ones count.
            distance <= max_distance,
        )
        # ORDER BY the distance alone, so Postgres can walk the HNSW index.
        .order_by(distance)
        .limit(BRANCH_LIMIT)
        .subquery()
    )
    return select(
        top.c.id,
        func.row_number().over(order_by=(top.c.distance, top.c.id)).label("rank"),
    )


async def hybrid_search(
    session: AsyncSession,
    user_id: UUID,
    *,
    q: str,
    vector: list[float] | None,
    mode: Mode,
    filters: Filters,
    max_distance: float,
    limit: int,
) -> list[Hit]:
    conditions = _owned(user_id, filters)
    keyword = (
        _keyword_branch(q, conditions).cte("keyword") if mode in ("keyword", "hybrid") else None
    )
    semantic = (
        _semantic_branch(vector, max_distance, conditions).cte("semantic")
        if mode in ("semantic", "hybrid") and vector is not None
        else None
    )
    fused = fuse(keyword, semantic)
    if fused is None:
        return []
    rows = await session.execute(
        select(Snippet, fused.c.score, fused.c.by_keyword, fused.c.by_semantic)
        .join(fused, Snippet.id == fused.c.id)
        .where(Snippet.user_id == user_id)  # belt and braces: the join is already scoped
        .order_by(fused.c.score.desc(), Snippet.id)
        .limit(limit)
    )
    return [
        Hit(
            snippet=snippet,
            score=float(score),
            match_type="both"
            if by_keyword and by_semantic
            else ("keyword" if by_keyword else "semantic"),
        )
        for snippet, score, by_keyword, by_semantic in rows
    ]


__all__ = ["BRANCH_LIMIT", "RRF_K", "Filters", "Hit", "Mode", "hybrid_search"]
