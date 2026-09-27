import math
import uuid

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.models import Snippet
from app.services.ai.embedding_text import MAX_CHARS, content_hash, embedding_text
from app.services.ai.embeddings import (
    FakeEmbeddingProvider,
    check_embedding_config,
    model_dimension,
)
from app.workers import dispatch


def snippet(**fields: object) -> Snippet:
    defaults: dict[str, object] = {
        "title": "Debounce",
        "description": "Delay a call",
        "code": "debounce()",
        "language": "javascript",
        "tags": ["timing", "react"],
    }
    return Snippet(**(defaults | fields))


def test_embedding_text_leads_with_intent_and_ends_with_code() -> None:
    assert (
        embedding_text(snippet()) == "Debounce\nDelay a call\ntiming react\njavascript\ndebounce()"
    )


def test_embedding_text_skips_empty_parts_and_is_capped() -> None:
    text = embedding_text(snippet(description=None, language=None, tags=[], code="x" * 10_000))
    assert text.startswith("Debounce\nxxx")
    assert len(text) == MAX_CHARS


def test_content_hash_changes_with_text_or_model() -> None:
    base = content_hash("text", "model-a")
    assert base == content_hash("text", "model-a")
    assert base != content_hash("text!", "model-a")
    assert base != content_hash("text", "model-b")  # a new model must re-embed everything


async def test_fake_vectors_are_unit_length_deterministic_and_word_based() -> None:
    fake = FakeEmbeddingProvider()
    [a, again, other] = await fake.embed_documents(["red apple", "red apple", "blue car"])
    assert a == again
    assert math.isclose(sum(x * x for x in a), 1.0)
    assert sum(x * y for x, y in zip(a, other, strict=True)) == 0  # no shared words


async def test_fake_aliases_stage_a_semantic_match() -> None:
    fake = FakeEmbeddingProvider(aliases={"intent query": "red apple"})
    assert await fake.embed_query("intent query") == fake.vector("red apple")


def test_the_real_models_dimension_comes_from_the_catalogue() -> None:
    assert model_dimension("BAAI/bge-small-en-v1.5") == 384
    assert model_dimension("not/a-model") is None


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "embedding_provider": "fastembed",
        "jwt_secret": SecretStr("x" * 40),
    }
    return Settings(_env_file=None, **(values | overrides))  # type: ignore[call-arg, arg-type]


def test_startup_check_catches_a_dimension_mismatch() -> None:
    check_embedding_config(settings())  # 384 matches: fine
    with pytest.raises(RuntimeError, match="384-dimensional"):
        check_embedding_config(settings(embedding_dim=768))
    with pytest.raises(RuntimeError, match="Unknown embedding model"):
        check_embedding_config(settings(embedding_model="not/a-model"))
    check_embedding_config(settings(embedding_provider="fake", embedding_dim=3))  # skipped


async def test_a_failed_enqueue_does_not_fail_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.workers import tasks

    async def redis_down(*_: object) -> None:
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(tasks.embed_snippet_task, "kiq", redis_down)
    await dispatch.TaskiqDispatcher().embed_snippet(uuid.uuid4())  # logs, doesn't raise
