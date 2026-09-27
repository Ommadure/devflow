"""The real Postgres, Redis and migrations — no fakes."""

import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.rate_limit import RedisRateLimiter, Rule
from app.db.base import Base
from app.main import create_app
from tests.conftest import TEST_REDIS_URL


@pytest.fixture
async def redis() -> Redis:
    client: Redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await client.flushdb()
    return client


async def test_models_and_migrations_agree(migrated_database: str) -> None:
    """Fails when a model changes without a migration (or the other way round)."""
    engine = create_async_engine(migrated_database, poolclass=NullPool)
    async with engine.connect() as conn:
        diff = await conn.run_sync(
            lambda sync: compare_metadata(MigrationContext.configure(sync), Base.metadata)
        )
    await engine.dispose()
    assert diff == []


async def test_ready_against_real_postgres_and_redis(migrated_database: str, redis: Redis) -> None:
    real = create_app()  # no overrides: the real checks against the test services
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=real), base_url="https://test"
    ) as client:
        response = await client.get("/ready")
    assert response.status_code == 200, response.text
    assert response.json()["checks"] == {"database": "ok", "redis": "ok"}


async def test_redis_rate_limiter_counts_and_expires(redis: Redis) -> None:
    limiter = RedisRateLimiter(redis, prefix="test")
    rule = Rule(limit=2, window_seconds=60)
    first, second, third = [await limiter.hit("k", rule) for _ in range(3)]
    assert first.allowed and second.allowed
    assert not third.allowed
    assert 0 < third.retry_after <= 60
    assert 0 < await redis.ttl("test:k") <= 60  # the key always has an expiry


async def test_redis_rate_limiter_keys_are_independent(redis: Redis) -> None:
    limiter = RedisRateLimiter(redis, prefix="test")
    rule = Rule(limit=1, window_seconds=60)
    assert (await limiter.hit("a", rule)).allowed
    assert (await limiter.hit("b", rule)).allowed


async def test_sliding_window_counts_the_last_n_seconds(redis: Redis) -> None:
    from app.core.rate_limit import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(redis, prefix="test-sliding")
    rule = Rule(limit=3, window_seconds=60)
    decisions = [await limiter.hit("user", rule) for _ in range(4)]
    assert [d.allowed for d in decisions] == [True, True, True, False]
    assert 55 <= decisions[-1].retry_after <= 60  # until the oldest hit leaves the window
    assert await redis.zcard("test-sliding:user") == 3  # refused hits aren't recorded
