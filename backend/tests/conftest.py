# ruff: noqa: E402  (env vars must be set before app modules are imported)
import os

# Must be set before any app module reads settings. Tests never need real credentials.
os.environ["APP_ENV"] = "test"
# Integration tests use their own database and Redis db so they can't touch dev data.
# Defaults = the docker compose services (host ports 5434 / 6380); CI overrides them.
TEST_DATABASE_URL = os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+asyncpg://devflow:devflow@localhost:5434/devflow_test"
)
TEST_REDIS_URL = os.environ.setdefault("TEST_REDIS_URL", "redis://localhost:6380/15")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.pop("DATABASE_DIRECT_URL", None)
os.environ["REDIS_URL"] = TEST_REDIS_URL

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import make_url, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.api.deps import get_rate_limiter
from app.core.config import Settings, get_settings
from app.core.passwords import get_password_hasher
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from tests.helpers import ORIGIN, TEST_JWT_SECRET, InMemoryRateLimiter, fast_hasher

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
        jwt_secret=TEST_JWT_SECRET,  # type: ignore[arg-type]
        cors_origins=ORIGIN,
    )


@pytest.fixture
def limiter() -> InMemoryRateLimiter:
    return InMemoryRateLimiter()


@pytest.fixture
def app(settings: Settings, limiter: InMemoryRateLimiter) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[get_password_hasher] = fast_hasher
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """In-process client with no database: for routes that don't touch one."""
    async with _client(app) as test_client:
        yield test_client


def _client(app: FastAPI) -> httpx.AsyncClient:
    # ASGITransport calls the app in-process: no server, no network. https, so the
    # client's cookie jar sends Secure cookies back — exactly like a browser would.
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test")


# ---- database (integration tests) ----


@pytest.fixture(scope="session")
def migrated_database() -> str:
    """Create the test database once and run the real Alembic migrations on it.

    Going down to "base" and back up also proves every downgrade works.
    """
    url = make_url(TEST_DATABASE_URL)
    try:
        asyncio.run(_ensure_database_exists(url))
    except OSError as exc:
        pytest.fail(
            f"Integration tests need Postgres at {url.render_as_string(hide_password=True)}. "
            f"Start it with `docker compose up -d`. ({exc})"
        )
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return TEST_DATABASE_URL


async def _ensure_database_exists(url: URL) -> None:
    admin = create_async_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    await admin.dispose()


@pytest.fixture
async def sessionmaker(migrated_database: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # NullPool: each test has its own event loop, and pooled asyncpg connections can't
    # move between loops.
    engine = create_async_engine(migrated_database, poolclass=NullPool)
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def api(
    app: FastAPI, sessionmaker: async_sessionmaker[AsyncSession]
) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client for the app wired to the migrated, emptied test database."""

    async def test_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    async with _client(app) as test_client:
        yield test_client
