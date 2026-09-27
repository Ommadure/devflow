"""GitHub's public API, called by the server (spec §11.8).

- A server-side token: 5,000 requests an hour instead of 60 per visitor's IP.
- Responses cached in Redis for 15 minutes; after that, revalidated with the stored ETag
  (If-None-Match). A 304 "not modified" answer doesn't count against the rate limit.
- A hit rate limit is a clear GITHUB_RATE_LIMITED error that says when it resets.
- Usernames are validated before they're put in a URL path.
"""

import json
import re
import time
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import httpx
import structlog
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.errors import NotFoundError, RateLimitedError, UpstreamError, ValidationFailedError

log = structlog.get_logger()

# GitHub's rule: 1-39 alphanumerics or single hyphens, not starting or ending with one.
USERNAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
FRESH_SECONDS = 15 * 60
KEEP_SECONDS = 24 * 60 * 60  # the ETag stays useful long after the body goes stale


def validate_username(username: str) -> str:
    if not USERNAME.fullmatch(username):
        raise ValidationFailedError(
            "That isn't a valid GitHub username.", code="INVALID_GITHUB_USERNAME"
        )
    return username


@lru_cache
def github_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15)


def build_github_client(settings: Settings, redis: Redis) -> "GitHubClient":
    return GitHubClient(
        github_http_client(),
        redis,
        token=settings.github_token.get_secret_value(),
        base_url=settings.github_api_url,
    )


class GitHubClient:
    def __init__(
        self, http: httpx.AsyncClient, redis: Redis, *, token: str = "", base_url: str
    ) -> None:
        self._http = http
        self._redis = redis
        self._token = token
        self._base_url = base_url.rstrip("/")

    async def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        key = (
            "gh:"
            + path
            + ("?" + "&".join(f"{k}={v}" for k, v in sorted(params.items())) if params else "")
        )
        cached = await self._cached(key)
        if cached and time.time() - cached["fetched_at"] < FRESH_SECONDS:
            return cached["body"]

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DevFlow",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if cached and cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        try:
            response = await self._http.get(
                f"{self._base_url}{path}", params=params, headers=headers
            )
        except httpx.HTTPError as exc:
            raise UpstreamError("GitHub couldn't be reached.", code="GITHUB_UNAVAILABLE") from exc

        if response.status_code == 304 and cached:
            await self._store(key, cached["body"], cached.get("etag"))  # fresh again, for free
            return cached["body"]
        if response.status_code == 404:
            raise NotFoundError("No such GitHub user.", code="GITHUB_USER_NOT_FOUND")
        if response.status_code in (403, 429) and (
            response.headers.get("x-ratelimit-remaining") == "0" or response.status_code == 429
        ):
            reset = int(response.headers.get("x-ratelimit-reset", time.time() + 60))
            at = datetime.fromtimestamp(reset, UTC).strftime("%H:%M UTC")
            raise RateLimitedError(
                max(1, reset - int(time.time())),
                f"GitHub's rate limit is used up; it resets at {at}.",
                code="GITHUB_RATE_LIMITED",
            )
        if response.is_error:
            log.warning("github.error", status=response.status_code, path=path)
            raise UpstreamError("GitHub returned an error.", code="GITHUB_UNAVAILABLE")
        body = response.json()
        await self._store(key, body, response.headers.get("etag"))
        return body

    async def _cached(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self._redis.get(key)
        except Exception:
            return None  # cache is best-effort
        return json.loads(raw) if raw else None

    async def _store(self, key: str, body: Any, etag: str | None) -> None:
        try:
            await self._redis.set(
                key,
                json.dumps({"body": body, "etag": etag, "fetched_at": time.time()}),
                ex=KEEP_SECONDS,
            )
        except Exception:
            log.warning("github.cache_unavailable")

    # ---- what DevFlow shows ----

    async def overview(self, username: str) -> dict[str, Any]:
        username = validate_username(username)
        profile = await self.get(f"/users/{username}")
        repos = await self.get(f"/users/{username}/repos", {"sort": "updated", "per_page": "6"})
        return {"profile": profile, "repos": repos}

    async def public_events(self, username: str) -> list[dict[str, Any]]:
        """Up to 100 recent public events (GitHub keeps 90 days)."""
        events: list[dict[str, Any]] = await self.get(
            f"/users/{validate_username(username)}/events/public", {"per_page": "100"}
        )
        return events
