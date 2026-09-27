"""Data access for snippets. Every function takes `user_id` and filters by it (ADR 0002):
another user's snippet is indistinguishable from one that doesn't exist."""

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, keyset
from app.models import Snippet
from app.repositories._text import like_pattern


async def list_page(
    session: AsyncSession,
    user_id: UUID,
    params: PageParams,
    *,
    q: str | None = None,
    language: str | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
) -> list[Snippet]:
    """Up to limit+1 snippets, newest first (see `keyset`)."""
    stmt = select(Snippet).where(Snippet.user_id == user_id)
    if q:
        # A plain substring filter for now; Phase 4 replaces it with hybrid search.
        pattern = like_pattern(q)
        stmt = stmt.where(
            or_(
                Snippet.title.ilike(pattern, escape="\\"),
                Snippet.description.ilike(pattern, escape="\\"),
                Snippet.code.ilike(pattern, escape="\\"),
            )
        )
    if language:
        stmt = stmt.where(Snippet.language == language)
    if tag:
        stmt = stmt.where(Snippet.tags.contains([tag]))
    if favorite is not None:
        stmt = stmt.where(Snippet.favorite.is_(favorite))
    result = await session.scalars(keyset(stmt, Snippet.created_at, Snippet.id, params))
    return list(result)


async def get(session: AsyncSession, user_id: UUID, snippet_id: UUID) -> Snippet | None:
    return await session.scalar(
        select(Snippet).where(Snippet.id == snippet_id, Snippet.user_id == user_id)
    )


async def add(session: AsyncSession, user_id: UUID, **fields: Any) -> Snippet:
    snippet = Snippet(user_id=user_id, **fields)
    session.add(snippet)
    await session.flush()
    return snippet


async def delete_one(session: AsyncSession, user_id: UUID, snippet_id: UUID) -> bool:
    deleted = await session.scalar(
        delete(Snippet)
        .where(Snippet.id == snippet_id, Snippet.user_id == user_id)
        .returning(Snippet.id)
    )
    return deleted is not None


async def tag_counts(session: AsyncSession, user_id: UUID) -> list[tuple[str, int]]:
    """Every tag this user has used, most used first: the filter chips."""
    tag = func.unnest(Snippet.tags).label("tag")
    inner = select(tag).where(Snippet.user_id == user_id).subquery()
    rows = await session.execute(
        select(inner.c.tag, func.count().label("uses"))
        .group_by(inner.c.tag)
        .order_by(func.count().desc(), inner.c.tag)
    )
    return [(row.tag, row.uses) for row in rows]


async def count(session: AsyncSession, user_id: UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(Snippet).where(Snippet.user_id == user_id)
        )
        or 0
    )
