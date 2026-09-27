"""Snippet search: embeds the query (cached), runs the hybrid query, shapes the result."""

import hashlib
import json
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.repositories.search import Filters, Mode, hybrid_search
from app.schemas.snippets import SearchHit, SearchResults, SnippetOut
from app.services.ai.embeddings import EmbeddingProvider, Vector

log = structlog.get_logger()

# Cosine distance 0.4 = similarity 0.6. bge-small scores unrelated text around 0.4 to 0.55 and
# real matches 0.65+ (measured on our own snippets). The Phase 7 evaluation tunes this.
DEFAULT_MAX_DISTANCE = 0.4


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        provider: EmbeddingProvider,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._provider = provider
        self._redis = redis
        self._settings = settings

    async def search(self, q: str, *, mode: Mode, filters: Filters, limit: int) -> SearchResults:
        vector = await self._query_vector(q) if mode != "keyword" else None
        hits = await hybrid_search(
            self._session,
            self._user_id,
            q=q,
            vector=vector,
            mode=mode,
            filters=filters,
            max_distance=DEFAULT_MAX_DISTANCE,
            limit=limit,
        )
        return SearchResults(
            items=[
                SearchHit(
                    **SnippetOut.model_validate(hit.snippet).model_dump(),
                    score=round(hit.score, 6),
                    match_type=hit.match_type,
                )
                for hit in hits
            ]
        )

    async def _query_vector(self, q: str) -> Vector:
        """Embedding a query costs ~10 ms of CPU; the same query (typing pauses, paging,
        switching modes) comes back from Redis instead. The cache is best-effort: if Redis
        is down, search still works, just without it."""
        key = "qemb:" + hashlib.sha256(f"{self._provider.model_name}\n{q}".encode()).hexdigest()
        ttl = self._settings.query_embedding_cache_seconds
        if ttl:
            try:
                cached = await self._redis.get(key)
                if cached:
                    return list(json.loads(cached))
            except Exception:
                log.warning("search.cache_unavailable", exc_info=True)
        vector = await self._provider.embed_query(q)
        if ttl:
            try:
                await self._redis.set(key, json.dumps(vector), ex=ttl)
            except Exception:
                log.warning("search.cache_unavailable", exc_info=True)
        return vector
