"""Data access for users.

Auth is the one place that looks users up *before* knowing who is asking (by email at
login). Every repository for user-owned data (snippets, notes, …) takes `user_id` and
filters by it instead.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def add(session: AsyncSession, *, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    await session.flush()  # sends the INSERT, so a duplicate email fails here
    await session.refresh(user)  # load server defaults (created_at)
    return user
