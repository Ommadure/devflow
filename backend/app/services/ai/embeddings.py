"""Text embeddings: turning text into 384 numbers whose direction captures meaning, so
"stop a function from firing too often" lands near a debounce snippet (ADR 0004).

The protocol keeps callers independent of the model. FastEmbed runs bge-small-en-v1.5
locally through ONNX Runtime (no PyTorch, no API bill); the fake gives deterministic vectors
so tests never download a model.
"""

import asyncio
import hashlib
import math
import re
from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

from app.core.config import Settings, get_settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding

Vector = list[float]


class EmbeddingProvider(Protocol):
    model_name: str
    dim: int

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]: ...

    async def embed_query(self, text: str) -> Vector: ...


class FastEmbedProvider:
    """bge-small-en-v1.5 via FastEmbed. BGE models are trained with an instruction prefix for
    queries but not for documents; query_embed/passage_embed apply the right one."""

    def __init__(self, model_name: str, dim: int, cache_dir: str, threads: int | None = None):
        self.model_name = model_name
        self.dim = dim
        self._cache_dir = cache_dir
        self._threads = threads
        self._model: TextEmbedding | None = None
        self._lock = asyncio.Lock()

    async def _load(self) -> "TextEmbedding":
        # Loaded on first use, once per process (~65 MB of weights).
        async with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._model = await asyncio.to_thread(
                    TextEmbedding, self.model_name, cache_dir=self._cache_dir, threads=self._threads
                )
        return self._model

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        model = await self._load()
        # Inference is CPU-bound: run it in a thread so the event loop keeps serving requests.
        vectors = await asyncio.to_thread(lambda: list(model.passage_embed(list(texts))))
        return [vector.tolist() for vector in vectors]

    async def embed_query(self, text: str) -> Vector:
        model = await self._load()
        vectors = await asyncio.to_thread(lambda: list(model.query_embed([text])))
        return [float(x) for x in vectors[0]]


class FakeEmbeddingProvider:
    """Deterministic "embeddings" for tests: a hashed bag of words, normalised.

    Texts sharing words point in similar directions, like a (very) crude real model.
    `aliases` makes a query embed exactly like some other text — how tests stage a match
    that is semantic only, with no words in common.
    """

    model_name = "fake-bag-of-words"

    def __init__(self, dim: int = 384, aliases: dict[str, str] | None = None) -> None:
        self.dim = dim
        self.aliases = aliases or {}

    def vector(self, text: str) -> Vector:
        values = [0.0] * self.dim
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dim
            values[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return [self.vector(text) for text in texts]

    async def embed_query(self, text: str) -> Vector:
        return self.vector(self.aliases.get(text, text))


def model_dimension(model_name: str) -> int | None:
    """The model's output size from FastEmbed's catalogue, without loading the model."""
    from fastembed import TextEmbedding

    for model in TextEmbedding.list_supported_models():
        if model["model"] == model_name:
            return int(model["dim"])
    return None


def check_embedding_config(settings: Settings) -> None:
    """Fail at startup, not on the first write, if EMBEDDING_DIM doesn't match the model:
    the database column is vector(EMBEDDING_DIM) and every insert would be rejected."""
    if settings.embedding_provider != "fastembed":
        return
    dim = model_dimension(settings.embedding_model)
    if dim is None:
        raise RuntimeError(f"Unknown embedding model: {settings.embedding_model}")
    if dim != settings.embedding_dim:
        raise RuntimeError(
            f"{settings.embedding_model} produces {dim}-dimensional vectors, "
            f"but EMBEDDING_DIM is {settings.embedding_dim}"
        )


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider(dim=settings.embedding_dim)
    return FastEmbedProvider(
        settings.embedding_model, settings.embedding_dim, settings.fastembed_cache_path
    )
