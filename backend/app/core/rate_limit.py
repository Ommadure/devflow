"""Rate limiting behind a small protocol, so routes don't care where counts live.

Phase 1 uses a fixed window in Redis: simple, one round trip, and good enough to stop
password guessing. Phase 5 replaces it with a sliding window for the AI routes, where a
burst at a window boundary (up to twice the limit) matters more.
"""

import hashlib
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis


@dataclass(frozen=True)
class Rule:
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int  # seconds until the window resets (meaningful when not allowed)


class RateLimiter(Protocol):
    async def hit(self, key: str, rule: Rule) -> Decision:
        """Count one use of `key` and say whether it is still within `rule`."""
        ...


class RedisRateLimiter:
    """INCR a per-window counter; the key expires when the window ends.

    INCR, EXPIRE NX and TTL run in one transaction (MULTI/EXEC), so a crash can never leave
    a counter without an expiry — which would lock the key out forever.
    """

    def __init__(self, redis: Redis, prefix: str = "rl") -> None:
        self._redis = redis
        self._prefix = prefix

    async def hit(self, key: str, rule: Rule) -> Decision:
        full_key = f"{self._prefix}:{key}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.incr(full_key)
            pipe.expire(full_key, rule.window_seconds, nx=True)
            pipe.ttl(full_key)
            count, _, ttl = await pipe.execute()
        return Decision(allowed=int(count) <= rule.limit, retry_after=max(int(ttl), 1))


def hashed(value: str) -> str:
    """Key part for personal data (emails): counts per person without storing who."""
    return hashlib.sha256(value.encode()).hexdigest()[:32]
