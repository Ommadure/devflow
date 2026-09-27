"""The real model, when it's on disk (a dev machine after the first run, the Docker image).

CI never downloads it, so these skip there. Run locally to check that the actual model
does what the fake one only pretends to: rank by meaning.
"""

import math
from pathlib import Path

import pytest

from app.services.ai.embeddings import FastEmbedProvider

CACHE = Path(__file__).resolve().parents[2] / ".cache" / "fastembed"

pytestmark = pytest.mark.skipif(
    not any(CACHE.glob("**/model_optimized.onnx")), reason="bge-small not downloaded"
)


@pytest.fixture(scope="module")
def model() -> FastEmbedProvider:
    return FastEmbedProvider("BAAI/bge-small-en-v1.5", 384, str(CACHE))


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    )


async def test_vectors_have_the_configured_dimension(model: FastEmbedProvider) -> None:
    [vector] = await model.embed_documents(["hello"])
    assert len(vector) == 384


async def test_intent_queries_land_nearest_the_right_snippet(model: FastEmbedProvider) -> None:
    snippets = {
        "debounce": "Debounce\nDelay a call until input settles\nfunction debounce(fn, ms) {}",
        "center": "Center a div\nflexbox\n.parent { display: flex; align-items: center; }",
        "upsert": "Upsert\nINSERT INTO users ... ON CONFLICT (id) DO UPDATE SET ...",
    }
    vectors = dict(zip(snippets, await model.embed_documents(list(snippets.values())), strict=True))
    for query, expected in [
        ("stop a function from firing too often", "debounce"),
        ("put an element in the middle of the page", "center"),
        ("insert or update if the row exists", "upsert"),
    ]:
        q = await model.embed_query(query)
        best = max(vectors, key=lambda name: cosine(q, vectors[name]))
        assert best == expected, query
