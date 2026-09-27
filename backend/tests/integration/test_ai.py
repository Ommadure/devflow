"""The AI routes end to end: SSE framing, quotas, limits, redaction, usage records."""

import json
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AiUsage
from app.services.ai import indexing
from app.services.ai.assistant import NOT_FOUND
from app.services.ai.chunking import chunk_embedding_text, chunk_note
from app.services.ai.embeddings import FakeEmbeddingProvider
from app.services.ai.llm.base import LLMError, LLMRateLimited
from app.services.ai.llm.fake import FakeLLMProvider
from tests.helpers import InMemoryRateLimiter
from tests.integration.conftest import Headers

Sessions = async_sessionmaker[AsyncSession]
SECRET = "sk_live_" + "q" * 24


def parse_sse(body: str) -> list[tuple[str, Any]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


async def snippet(api: httpx.AsyncClient, headers: Headers, **fields: Any) -> str:
    body = {"title": "Stripe client", "code": f'stripe = Stripe(api_key="{SECRET}")', **fields}
    response = await api.post("/api/v1/snippets", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def usage_rows(sessions: Sessions) -> list[AiUsage]:
    async with sessions() as session:
        return list(await session.scalars(select(AiUsage).order_by(AiUsage.created_at)))


# ---- explain (SSE) ----


async def test_explain_streams_tokens_then_done_and_records_usage(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider, sessionmaker: Sessions
) -> None:
    llm._default = "It **creates** a Stripe client."
    snippet_id = await snippet(api, alice)

    response = await api.post(
        f"/api/v1/snippets/{snippet_id}/ai/explain", json={"level": "beginner"}, headers=alice
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    events = parse_sse(response.text)
    assert "".join(data["text"] for event, data in events if event == "token") == llm._default
    assert events[-1][0] == "done"
    assert events[-1][1]["usage"]["output_tokens"] > 0

    [row] = await usage_rows(sessionmaker)
    assert (row.feature, row.status, row.prompt_version) == (
        "explain_code",
        "success",
        "explain_code_v1",
    )
    assert row.input_tokens > 0


async def test_secrets_never_reach_the_model(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider
) -> None:
    llm._script = ["An explanation.", GOOD_TAGS]
    snippet_id = await snippet(api, alice)
    await api.post(f"/api/v1/snippets/{snippet_id}/ai/explain", json={}, headers=alice)
    await api.post(f"/api/v1/snippets/{snippet_id}/ai/tags", headers=alice)
    sent = "\n".join(m.content for call in llm.calls for m in call)
    assert len(llm.calls) == 2  # both features really called the model
    assert SECRET not in sent
    assert sent.count("[REDACTED]") >= 2


async def test_the_level_shapes_the_prompt(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider
) -> None:
    snippet_id = await snippet(api, alice)
    await api.post(
        f"/api/v1/snippets/{snippet_id}/ai/explain", json={"level": "expert"}, headers=alice
    )
    assert "The reader's level: expert." in llm.calls[0][0].content


async def test_a_failure_mid_stream_ends_with_an_error_event(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions, llm: FakeLLMProvider
) -> None:
    llm._fail_stream_after = 2
    llm._default = "one two three four five"
    snippet_id = await snippet(api, alice)

    response = await api.post(f"/api/v1/snippets/{snippet_id}/ai/explain", json={}, headers=alice)

    events = parse_sse(response.text)
    assert [event for event, _ in events] == ["token", "token", "error"]
    assert events[-1][1]["code"] == "AI_FAILED"
    [row] = await usage_rows(sessionmaker)
    assert (row.status, row.error_code) == ("error", "LLM_ERROR")


async def test_explaining_someone_elses_snippet_is_404_and_costs_nothing(
    api: httpx.AsyncClient,
    alice: Headers,
    bob: Headers,
    llm: FakeLLMProvider,
    sessionmaker: Sessions,
) -> None:
    snippet_id = await snippet(api, alice)
    response = await api.post(f"/api/v1/snippets/{snippet_id}/ai/explain", json={}, headers=bob)
    assert response.status_code == 404
    assert llm.calls == [] and await usage_rows(sessionmaker) == []


# ---- quota and limits ----


async def test_the_daily_quota_is_a_429_before_any_stream(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider, sessionmaker: Sessions
) -> None:
    snippet_id = await snippet(api, alice)
    url = f"/api/v1/snippets/{snippet_id}/ai/explain"
    for _ in range(5):  # the test quota is 5
        assert (await api.post(url, json={}, headers=alice)).status_code == 200

    refused = await api.post(url, json={}, headers=alice)

    assert refused.status_code == 429
    assert refused.headers["content-type"] == "application/json"  # an error, not a stream
    assert refused.json()["error"]["code"] == "QUOTA_EXCEEDED"
    assert 0 < int(refused.headers["retry-after"]) <= 86_400
    assert len(llm.calls) == 5
    statuses = [row.status for row in await usage_rows(sessionmaker)]
    assert statuses == ["success"] * 5 + ["quota_exceeded"]

    usage = (await api.get("/api/v1/me/ai-usage", headers=alice)).json()
    assert (usage["used"], usage["limit"], usage["remaining"]) == (5, 5, 0)


async def test_ai_routes_are_rate_limited_per_minute(
    api: httpx.AsyncClient, alice: Headers, limiter: InMemoryRateLimiter
) -> None:
    snippet_id = await snippet(api, alice)
    limiter.counts[f"ai:user:{(await api.get('/api/v1/me', headers=alice)).json()['id']}"] = 10
    response = await api.post(f"/api/v1/snippets/{snippet_id}/ai/tags", headers=alice)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


async def test_every_signed_in_route_shares_a_general_limit(
    api: httpx.AsyncClient, alice: Headers, limiter: InMemoryRateLimiter
) -> None:
    me = (await api.get("/api/v1/me", headers=alice)).json()
    limiter.counts[f"api:user:{me['id']}"] = 120
    assert (await api.get("/api/v1/notes", headers=alice)).status_code == 429


# ---- auto-tag ----

GOOD_TAGS = json.dumps(
    {
        "language": "Python",
        "tags": ["Payments", "stripe api"],
        "description": "Creates a Stripe client.",
    }
)


async def test_tags_are_suggested_normalised_and_not_saved(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider, sessionmaker: Sessions
) -> None:
    llm._script = [GOOD_TAGS]
    snippet_id = await snippet(api, alice, tags=["mine"])

    response = await api.post(f"/api/v1/snippets/{snippet_id}/ai/tags", headers=alice)

    assert response.json() == {
        "language": "python",
        "tags": ["payments", "stripe-api"],
        "description": "Creates a Stripe client.",
    }
    stored = (await api.get(f"/api/v1/snippets/{snippet_id}", headers=alice)).json()
    assert stored["tags"] == ["mine"]  # the user's tags are never overwritten
    [row] = await usage_rows(sessionmaker)
    assert (row.feature, row.status) == ("auto_tag", "success")


async def test_invalid_json_gets_one_repair_attempt(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider, sessionmaker: Sessions
) -> None:
    llm._script = ['{"language": "python"}', GOOD_TAGS]
    snippet_id = await snippet(api, alice)

    response = await api.post(f"/api/v1/snippets/{snippet_id}/ai/tags", headers=alice)

    assert response.status_code == 200
    repair = llm.calls[1]
    assert repair[-2].role == "assistant" and repair[-2].content == '{"language": "python"}'
    assert "not valid" in repair[-1].content and "tags" in repair[-1].content
    assert [r.status for r in await usage_rows(sessionmaker)] == ["error", "success"]


async def test_two_invalid_answers_are_a_clean_502(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider
) -> None:
    llm._script = ["nope", "still nope"]
    snippet_id = await snippet(api, alice)
    response = await api.post(f"/api/v1/snippets/{snippet_id}/ai/tags", headers=alice)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_INVALID_OUTPUT"


async def test_provider_failures_map_to_clean_errors(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider
) -> None:
    snippet_id = await snippet(api, alice)
    url = f"/api/v1/snippets/{snippet_id}/ai/tags"
    llm._script = [LLMRateLimited("busy", retry_after=60), LLMError("boom")]
    busy, failed = await api.post(url, headers=alice), await api.post(url, headers=alice)
    assert (busy.status_code, busy.json()["error"]["code"]) == (503, "AI_BUSY")
    assert (failed.status_code, failed.json()["error"]["code"]) == (502, "AI_FAILED")


# ---- ask your notes ----

RUNBOOK = (
    "# Deploy\nRun the migrations, then restart the api container.\n\n"
    "# Coffee\nThe beans are in the left cupboard."
)


async def note(
    api: httpx.AsyncClient, headers: Headers, content: str, title: str = "Runbook"
) -> str:
    response = await api.post(
        "/api/v1/notes", json={"title": title, "content": content}, headers=headers
    )
    return str(response.json()["id"])


async def index(sessions: Sessions, embeddings: FakeEmbeddingProvider, note_id: str) -> None:
    async with sessions() as session:
        assert await indexing.embed_note(session, embeddings, uuid.UUID(note_id)) == "indexed"


async def test_no_relevant_passage_means_no_llm_call_and_no_cost(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider, sessionmaker: Sessions,
    embeddings: FakeEmbeddingProvider,
) -> None:  # fmt: skip
    note_id = await note(api, alice, RUNBOOK)
    await index(sessionmaker, embeddings, note_id)

    response = await api.post(
        "/api/v1/notes/ask", json={"question": "what is my wifi password"}, headers=alice
    )

    events = parse_sse(response.text)
    assert events == [
        ("sources", []),
        ("token", {"text": NOT_FOUND}),
        ("done", {"usage": {"input_tokens": 0, "output_tokens": 0}, "latency_ms": 0}),
    ]
    assert llm.calls == [] and await usage_rows(sessionmaker) == []


async def test_answers_cite_numbered_sources_from_the_right_passage(
    api: httpx.AsyncClient, alice: Headers, llm: FakeLLMProvider, sessionmaker: Sessions,
    embeddings: FakeEmbeddingProvider,
) -> None:  # fmt: skip
    note_id = await note(api, alice, RUNBOOK)
    await index(sessionmaker, embeddings, note_id)
    question = "how do I ship a release"
    deploy = next(c for c in chunk_note(RUNBOOK) if c.heading == "Deploy")
    embeddings.aliases[question] = chunk_embedding_text("Runbook", deploy)  # a meaning match
    llm._default = "Run the migrations, then restart the api [1]."

    response = await api.post("/api/v1/notes/ask", json={"question": question}, headers=alice)

    events = parse_sse(response.text)
    assert events[0][0] == "sources"
    first = events[0][1][0]
    assert (first["n"], first["note_id"], first["heading"]) == (1, note_id, "Deploy")
    assert "".join(d["text"] for e, d in events if e == "token") == llm._default
    prompt = llm.calls[0][-1].content
    assert "[1] (Runbook — Deploy)" in prompt and f"Question: {question}" in prompt
    [row] = await usage_rows(sessionmaker)
    assert (row.feature, row.status, row.prompt_version) == ("ask_notes", "success", "ask_notes_v1")


async def test_questions_only_see_your_own_notes(
    api: httpx.AsyncClient, alice: Headers, bob: Headers, llm: FakeLLMProvider,
    sessionmaker: Sessions, embeddings: FakeEmbeddingProvider,
) -> None:  # fmt: skip
    note_id = await note(api, alice, RUNBOOK)
    await index(sessionmaker, embeddings, note_id)
    question = "how do I ship a release"
    embeddings.aliases[question] = chunk_embedding_text("Runbook", chunk_note(RUNBOOK)[0])

    response = await api.post("/api/v1/notes/ask", json={"question": question}, headers=bob)

    assert parse_sse(response.text)[0] == ("sources", [])
    assert llm.calls == []


async def test_a_blank_question_is_422(api: httpx.AsyncClient, alice: Headers) -> None:
    assert (
        await api.post("/api/v1/notes/ask", json={"question": "  "}, headers=alice)
    ).status_code == 422
