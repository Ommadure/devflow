"""AI routes: explain a snippet (SSE), suggest its tags, ask your notes (SSE), usage.

Checks run in this order, all BEFORE a stream starts, so a refusal is an ordinary HTTP
error rather than an error event halfway through an answer:
rate limit (dependency) → the resource exists and is yours → daily quota → call the model.
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import (
    AiUsageDep,
    CurrentUserDep,
    EmbeddingsDep,
    LLMDep,
    SessionDep,
    SettingsDep,
    SnippetServiceDep,
    ai_rate_limit,
)
from app.schemas.ai import AiUsageOut, AskRequest, ExplainRequest, SnippetTagSuggestion
from app.services.ai import assistant

router = APIRouter(tags=["ai"])
limited = APIRouter(dependencies=[Depends(ai_rate_limit)])

SSE_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Server-Sent Events: `token`… then `done`, or `error`",
        "content": {"text/event-stream": {}},
    },
    404: {"description": "Not found (or not yours)"},
    429: {"description": "Rate limited, or the daily AI quota is used up"},
}


def event_stream(events: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            # Tell proxies (nginx, some CDNs) not to buffer: each token should arrive as
            # soon as it's produced, not in one lump at the end.
            "X-Accel-Buffering": "no",
        },
    )


@limited.post("/snippets/{snippet_id}/ai/explain", responses=SSE_RESPONSE)
async def explain_snippet(
    snippet_id: UUID,
    body: ExplainRequest,
    snippets: SnippetServiceDep,
    usage: AiUsageDep,
    llm: LLMDep,
) -> StreamingResponse:
    """Stream an explanation of the snippet, pitched at the requested level."""
    snippet = await snippets.get(snippet_id)
    await usage.check_quota("explain_code")
    messages = assistant.explain_messages(snippet, body.level)
    return event_stream(
        assistant.stream_answer(
            llm,
            messages,
            feature="explain_code",
            prompt_version=assistant.EXPLAIN_PROMPT,
            usage=usage,
        )
    )


@limited.post(
    "/snippets/{snippet_id}/ai/tags",
    responses={
        404: {"description": "Not found (or not yours)"},
        429: {"description": "Rate limited, or the daily AI quota is used up"},
        502: {"description": "The model's answer was unusable, even after one repair attempt"},
        503: {"description": "The AI provider is busy"},
    },
)
async def suggest_snippet_tags(
    snippet_id: UUID, snippets: SnippetServiceDep, usage: AiUsageDep, llm: LLMDep
) -> SnippetTagSuggestion:
    """Suggested language, tags and description. Nothing is saved: the user picks."""
    snippet = await snippets.get(snippet_id)
    await usage.check_quota("auto_tag")
    return await assistant.suggest_tags(llm, snippet, usage)


@limited.post("/notes/ask", responses=SSE_RESPONSE)
async def ask_notes(
    body: AskRequest,
    current: CurrentUserDep,
    session: SessionDep,
    embeddings: EmbeddingsDep,
    usage: AiUsageDep,
    llm: LLMDep,
    settings: SettingsDep,
) -> StreamingResponse:
    """Answer from the user's notes: `sources` first, then the cited answer."""
    hits = await assistant.retrieve(
        session, current.id, body.question, embeddings, settings.notes_min_similarity
    )
    if not hits:
        return event_stream(assistant.not_found_answer())  # no LLM call, no quota used
    await usage.check_quota("ask_notes")
    sources = assistant.sources_for(hits)
    return event_stream(
        assistant.stream_answer(
            llm,
            assistant.ask_messages(body.question, hits),
            feature="ask_notes",
            prompt_version=assistant.ASK_PROMPT,
            usage=usage,
            before=[assistant.sse("sources", [s.model_dump(mode="json") for s in sources])],
        )
    )


@router.get("/me/ai-usage")
async def ai_usage(usage: AiUsageDep) -> AiUsageOut:
    """Today's AI requests, for the "12/50 left today" indicator."""
    status = await usage.quota()
    return AiUsageOut(
        used=status.used, limit=status.limit, remaining=status.remaining, resets_at=status.resets_at
    )


router.include_router(limited)
