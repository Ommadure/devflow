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
# Deterministic vectors; tests never download or run the real model.
os.environ["EMBEDDING_PROVIDER"] = "fake"
os.environ["LLM_PROVIDER"] = "fake"

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import make_url, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.api.deps import get_rate_limiter, get_sliding_limiter
from app.core.config import Settings, get_settings
from app.core.passwords import get_password_hasher
from app.core.redis import get_redis
from app.db.base import Base
from app.db.session import get_engine, get_session, get_sessionmaker
from app.main import create_app
from app.services.ai.embeddings import FakeEmbeddingProvider, get_embedding_provider
from app.services.ai.llm.factory import get_llm_provider
from app.services.ai.llm.fake import FakeLLMProvider
from app.workers.dispatch import get_dispatcher
from tests.helpers import (
    ORIGIN,
    TEST_JWT_SECRET,
    InMemoryRateLimiter,
    RecordingDispatcher,
    fast_hasher,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _fresh_singletons() -> Iterator[None]:
    """Settings, the Redis client and the DB engine are cached once per process in the app.
    Each test runs in its own event loop, and asyncio connections can't cross loops, so
    every test starts with fresh ones."""
    caches = (get_settings, get_redis, get_engine, get_sessionmaker)
    for cached in caches:
        cached.cache_clear()
    yield
    for cached in caches:
        cached.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
        jwt_secret=TEST_JWT_SECRET,  # type: ignore[arg-type]
        cors_origins=ORIGIN,
        embedding_provider="fake",
        llm_provider="fake",
        ai_daily_quota_per_user=5,
    )


@pytest.fixture
def limiter() -> InMemoryRateLimiter:
    return InMemoryRateLimiter()


@pytest.fixture
def dispatcher() -> RecordingDispatcher:
    return RecordingDispatcher()


@pytest.fixture
def embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def llm() -> FakeLLMProvider:
    """No test ever calls a real (paid) model."""
    return FakeLLMProvider()


@pytest.fixture
def app(
    settings: Settings,
    limiter: InMemoryRateLimiter,
    dispatcher: RecordingDispatcher,
    embeddings: FakeEmbeddingProvider,
    llm: FakeLLMProvider,
) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[get_sliding_limiter] = lambda: limiter
    app.dependency_overrides[get_password_hasher] = fast_hasher
    # Jobs are recorded, not queued: no test needs a running worker.
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher
    app.dependency_overrides[get_embedding_provider] = lambda: embeddings
    app.dependency_overrides[get_llm_provider] = lambda: llm
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
    # One pooled engine per test: connections are reused across the test's requests
    # (opening one costs ~50 ms of TCP + SCRAM auth), and the engine is disposed at the
    # end — asyncpg connections can't move to the next test's event loop.
    engine = create_async_engine(migrated_database, pool_size=5)
    # DELETE, not TRUNCATE: the tables hold a handful of rows, and TRUNCATE recreates the
    # files of every table and index (HNSW, GIN) each time — most of a test's setup.
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
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
    # AI usage is recorded through its own sessions (after a stream ends): same test DB.
    app.dependency_overrides[get_sessionmaker] = lambda: sessionmaker
    # Redis db 15 holds rate-limit counters and cached query vectors; start each test empty.
    redis: Redis = Redis.from_url(TEST_REDIS_URL)
    await redis.flushdb()
    await redis.aclose()
    async with _client(app) as test_client:
        yield test_client
