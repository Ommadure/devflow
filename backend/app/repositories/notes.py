"""Data access for notes, always scoped to one user (ADR 0002)."""

from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, keyset
from app.models import Note
from app.repositories._text import like_pattern


async def list_page(
    session: AsyncSession, user_id: UUID, params: PageParams, *, q: str | None = None
) -> list[Note]:
    """Up to limit+1 notes, most recently updated first."""
    stmt = select(Note).where(Note.user_id == user_id)
    if q:
        pattern = like_pattern(q)
        stmt = stmt.where(
            or_(Note.title.ilike(pattern, escape="\\"), Note.content.ilike(pattern, escape="\\"))
        )
    result = await session.scalars(keyset(stmt, Note.updated_at, Note.id, params))
    return list(result)


async def get(session: AsyncSession, user_id: UUID, note_id: UUID) -> Note | None:
    return await session.scalar(select(Note).where(Note.id == note_id, Note.user_id == user_id))


async def add(session: AsyncSession, user_id: UUID, *, title: str, content: str) -> Note:
    note = Note(user_id=user_id, title=title, content=content)
    session.add(note)
    await session.flush()
    return note


async def delete_one(session: AsyncSession, user_id: UUID, note_id: UUID) -> bool:
    deleted = await session.scalar(
        delete(Note).where(Note.id == note_id, Note.user_id == user_id).returning(Note.id)
    )
    return deleted is not None


async def count(session: AsyncSession, user_id: UUID) -> int:
    return (
        await session.scalar(select(func.count()).select_from(Note).where(Note.user_id == user_id))
        or 0
    )
