"""Data access for completed focus sessions, always scoped to one user (ADR 0002)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, keyset
from app.models import PomodoroSession


async def add(session: AsyncSession, user_id: UUID, *, duration_seconds: int) -> PomodoroSession:
    record = PomodoroSession(user_id=user_id, duration_seconds=duration_seconds)
    session.add(record)
    await session.flush()
    return record


async def list_page(
    session: AsyncSession, user_id: UUID, params: PageParams
) -> list[PomodoroSession]:
    stmt = select(PomodoroSession).where(PomodoroSession.user_id == user_id)
    result = await session.scalars(
        keyset(stmt, PomodoroSession.completed_at, PomodoroSession.id, params)
    )
    return list(result)


async def count(session: AsyncSession, user_id: UUID, *, since: datetime | None = None) -> int:
    stmt = (
        select(func.count()).select_from(PomodoroSession).where(PomodoroSession.user_id == user_id)
    )
    if since is not None:
        stmt = stmt.where(PomodoroSession.completed_at >= since)
    return await session.scalar(stmt) or 0
