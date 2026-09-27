"""Async database engine and the per-request session."""

import uuid
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings, is_transaction_pooler


def engine_options(url: str) -> dict[str, Any]:
    """Pool settings, plus the fixes a transaction pooler (Neon's PgBouncer) needs.

    With transaction pooling, consecutive statements from one client may run on different
    server connections. A statement asyncpg prepared on one connection doesn't exist on the
    next, so caching prepared statements (asyncpg's and SQLAlchemy's) must be off, and each
    statement needs a unique name so two clients never collide on one server connection.
    """
    options: dict[str, Any] = {"pool_size": 5, "max_overflow": 5, "pool_pre_ping": True}
    if is_transaction_pooler(url):
        options["connect_args"] = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        }
    return options


@lru_cache
def get_engine() -> AsyncEngine:
    url = get_settings().database_url
    return create_async_engine(url, **engine_options(url))


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay readable after commit (we return them as JSON).
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, rolled back if the request fails.

    Services commit explicitly at the end of a unit of work; anything uncommitted when
    the request ends is discarded.
    """
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
