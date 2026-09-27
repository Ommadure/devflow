"""Test doubles and small helpers shared by unit and integration tests."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher as Argon2Hasher

from app.core.passwords import PasswordHasher
from app.core.rate_limit import Decision, Rule
from app.core.tokens import JWT_AUDIENCE, JWT_ISSUER

TEST_JWT_SECRET = "test-secret-" + "x" * 40
ORIGIN = "http://localhost:5173"
STRONG_PASSWORD = "Correct-Horse-9"


class RecordingDispatcher:
    """Stands in for Taskiq: remembers which jobs would have been queued."""

    def __init__(self) -> None:
        self.embeds: list[UUID] = []
        self.notes: list[UUID] = []

    async def embed_snippet(self, snippet_id: UUID) -> None:
        self.embeds.append(snippet_id)

    async def embed_note(self, note_id: UUID) -> None:
        self.notes.append(note_id)


class InMemoryRateLimiter:
    """Counts hits per key without Redis; windows never expire within a test."""

    def __init__(self) -> None:
        self.counts: defaultdict[str, int] = defaultdict(int)

    async def hit(self, key: str, rule: Rule) -> Decision:
        self.counts[key] += 1
        return Decision(allowed=self.counts[key] <= rule.limit, retry_after=rule.window_seconds)


def fast_hasher() -> PasswordHasher:
    """Real argon2id with tiny costs: the same code paths, milliseconds instead of ~50 ms."""
    return PasswordHasher(Argon2Hasher(time_cost=1, memory_cost=1024, parallelism=1))


def make_token(
    claims: dict[str, Any] | None = None,
    *,
    drop: tuple[str, ...] = (),
    secret: str = TEST_JWT_SECRET,
    algorithm: str = "HS256",
) -> str:
    """Mint an access token with any claims we like, to test every way one can be wrong."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": "7d3f8a2e-5b1c-4e9f-a6d0-2c8b1e4f7a90",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    payload.update(claims or {})
    for claim in drop:
        payload.pop(claim, None)
    return jwt.encode(payload, secret, algorithm=algorithm)
