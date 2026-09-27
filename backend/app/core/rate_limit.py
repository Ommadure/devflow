"""Rate limiting behind a small protocol, so routes don't care where counts live.

Two implementations behind one protocol:
- RedisRateLimiter, a fixed window: simple, one round trip, good enough to stop password
  guessing (auth routes).
- SlidingWindowRateLimiter: exact "N per last minute", for the general API limit and the
  expensive AI routes, where a burst at a window boundary (up to twice the limit) matters.
"""

import hashlib
import math
import time
import uuid
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


# Atomic in Redis (a script runs without interleaving): drop timestamps older than the
# window, count what's left, admit and record this hit only if under the limit. A fixed
# window lets a client send `limit` requests at 0:59 and `limit` more at 1:00; a sliding
# window counts the last 60 seconds at every moment.
_SLIDING_WINDOW = """
local key, member = KEYS[1], ARGV[4]
local now, window, limit = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
if redis.call('ZCARD', key) < limit then
  redis.call('ZADD', key, now, member)
  redis.call('PEXPIRE', key, window)
  return 0
end
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
return oldest[2] + window - now
"""


class SlidingWindowRateLimiter:
    """Timestamps of recent hits in a sorted set; used for the general and AI limits."""

    def __init__(self, redis: Redis, prefix: str = "rls") -> None:
        self._redis = redis
        self._prefix = prefix
        self._script = redis.register_script(_SLIDING_WINDOW)

    async def hit(self, key: str, rule: Rule) -> Decision:
        now_ms = int(time.time() * 1000)
        wait_ms = int(
            await self._script(
                keys=[f"{self._prefix}:{key}"],
                args=[
                    now_ms,
                    rule.window_seconds * 1000,
                    rule.limit,
                    f"{now_ms}-{uuid.uuid4().hex}",
                ],
            )
        )
        return Decision(allowed=wait_ms == 0, retry_after=max(1, math.ceil(wait_ms / 1000)))
