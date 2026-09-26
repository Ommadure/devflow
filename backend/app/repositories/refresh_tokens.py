"""Data access for refresh tokens (looked up by hash — the caller is not known yet)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken


async def add(
    session: AsyncSession,
    *,
    user_id: UUID,
    token_hash: str,
    family_id: UUID,
    expires_at: datetime,
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id, token_hash=token_hash, family_id=family_id, expires_at=expires_at
    )
    session.add(token)
    await session.flush()
    return token


async def get_by_hash_for_update(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    """Lock the row until commit, so two refreshes of one token run one after the other
    instead of both succeeding."""
    return await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    )


async def revoke_family(session: AsyncSession, family_id: UUID, now: datetime) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def revoke_all_for_user(session: AsyncSession, user_id: UUID, now: datetime) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
