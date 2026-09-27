"""The three AI features: explain a snippet (streamed), suggest tags (structured), and
answer questions from notes (streamed, with sources). Everything the model sees is
redacted first; every call is recorded in ai_usage.
"""

import asyncio
import json
import time
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from contextlib import aclosing
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import anyio
import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ServiceUnavailableError, UpstreamError
from app.models import Snippet
from app.repositories.note_search import ChunkHit, search_chunks
from app.schemas.ai import SnippetTagSuggestion, Source
from app.schemas.api_tester import ExplainErrorRequest, HttpErrorExplanation
from app.services.ai.embeddings import EmbeddingProvider
from app.services.ai.llm.base import (
    LLMError,
    LLMInvalidOutput,
    LLMProvider,
    LLMRateLimited,
    Message,
    TokenUsage,
)
from app.services.ai.prompts import load
from app.services.ai.redaction import redact
from app.services.ai.usage import AiUsageService, Feature

log = structlog.get_logger()

EXPLAIN_PROMPT = "explain_code_v1"
TAGS_PROMPT = "auto_tag_v1"
ASK_PROMPT = "ask_notes_v1"

NOT_FOUND = "I couldn't find this in your notes."
MAX_SOURCES = 6


def sse(event: str, data: Any) -> str:
    """One Server-Sent Event: `event:` names it, `data:` carries JSON, a blank line ends it."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _clean(text: str) -> str:
    redacted, kinds = redact(text)
    if kinds:
        log.info("ai.redacted", kinds=sorted(set(kinds)))  # which kinds — never the values
    return redacted


# ---- streaming, shared by "explain" and "ask" ----


async def stream_answer(
    llm: LLMProvider,
    messages: list[Message],
    *,
    feature: Feature,
    prompt_version: str,
    usage: AiUsageService,
    before: Sequence[str] = (),
) -> AsyncGenerator[str, None]:
    """Relay the model's tokens as SSE: `token` events, then `done` (or `error`).

    Whatever happens — success, provider failure, or the user closing the panel mid-answer
    — one ai_usage row is written, with the tokens actually spent.
    """
    for event in before:
        yield event
    started = time.monotonic()
    status: str = "error"
    error_code: str | None = None
    spent = TokenUsage()
    try:
        # aclosing(): if the client disconnects, Starlette cancels this generator; closing
        # the provider's stream then closes the HTTP connection to the model, which stops
        # the generation and the billing — instead of waiting for garbage collection.
        async with aclosing(
            llm.stream(messages, temperature=0.3, max_output_tokens=1024)
        ) as chunks:
            async for chunk in chunks:
                if chunk.text:
                    yield sse("token", {"text": chunk.text})
                if chunk.usage is not None:
                    spent = chunk.usage
        status = "success"
        yield sse(
            "done",
            {
                "usage": {"input_tokens": spent.input_tokens, "output_tokens": spent.output_tokens},
                "latency_ms": _ms(started),
            },
        )
    except LLMRateLimited:
        error_code = "AI_BUSY"
        yield sse(
            "error",
            {"code": error_code, "message": "The AI service is busy. Try again in a minute."},
        )
    except LLMError as exc:
        error_code = exc.code
        spent = exc.usage if exc.usage.output_tokens else spent
        log.warning("ai.stream_failed", feature=feature, error=str(exc))
        yield sse(
            "error",
            {"code": "AI_FAILED", "message": "The AI service failed. Try again in a moment."},
        )
    except (asyncio.CancelledError, GeneratorExit):
        # The client went away. Two ways that reaches us: cancelled while awaiting the model
        # (CancelledError), or closed while paused at a `yield`, waiting for the previous
        # token to be sent (GeneratorExit). Both are disconnects; both must be recorded.
        error_code = "CLIENT_DISCONNECTED"
        raise
    finally:
        # Shielded: when the client disconnected we're being cancelled, and an unshielded
        # await here would be cancelled too — losing the record of what was spent.
        with anyio.CancelScope(shield=True):
            await usage.record(
                feature, provider=llm.name, model=llm.model, status=status,  # type: ignore[arg-type]
                prompt_version=prompt_version, usage=spent, latency_ms=_ms(started),
                error_code=error_code,
            )  # fmt: skip


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


# ---- explain ----


def explain_messages(snippet: Snippet, level: str) -> list[Message]:
    language = snippet.language or "text"
    body = (
        f"Title: {_clean(snippet.title)}\n"
        + (f"Description: {_clean(snippet.description)}\n" if snippet.description else "")
        + f"Language: {language}\n\n```{language}\n{_clean(snippet.code)}\n```"
    )
    return [
        Message("system", load(EXPLAIN_PROMPT).replace("{level}", level)),
        Message("user", body),
    ]


# ---- auto-tag ----


async def structured_call[T: BaseModel](
    llm: LLMProvider,
    messages: list[Message],
    schema: type[T],
    *,
    feature: Feature,
    prompt_version: str,
    usage: AiUsageService,
    max_output_tokens: int = 400,
) -> T:
    """Structured output with one repair attempt: if the reply isn't valid, show the model
    its own reply and exactly what was wrong, and ask once more. Every attempt is recorded.
    """
    for attempt in (1, 2):
        started = time.monotonic()
        try:
            result = await llm.generate_structured(
                messages, schema, temperature=0.2, max_output_tokens=max_output_tokens
            )
        except LLMInvalidOutput as exc:
            await usage.record(
                feature, provider=llm.name, model=llm.model, status="error",
                prompt_version=prompt_version, usage=exc.usage, latency_ms=_ms(started),
                error_code=exc.code,
            )  # fmt: skip
            if attempt == 2:
                raise UpstreamError(
                    "The AI couldn't produce a usable answer. Try again.", code="AI_INVALID_OUTPUT"
                ) from exc
            messages = [
                *messages,
                Message("assistant", exc.raw_text),
                Message(
                    "user",
                    f"That reply was not valid ({exc.problem}). Reply again with only the JSON "
                    "object, in exactly the shape asked for.",
                ),
            ]
            continue
        except LLMError as exc:
            await usage.record(
                feature, provider=llm.name, model=llm.model, status="error",
                prompt_version=prompt_version, usage=exc.usage, latency_ms=_ms(started),
                error_code=exc.code,
            )  # fmt: skip
            if isinstance(exc, LLMRateLimited):
                raise ServiceUnavailableError(
                    "The AI service is busy. Try again in a minute.", code="AI_BUSY"
                ) from exc
            raise UpstreamError("The AI service failed. Try again.", code="AI_FAILED") from exc
        await usage.record(
            feature, provider=llm.name, model=llm.model, status="success",
            prompt_version=prompt_version, usage=result.usage, latency_ms=result.latency_ms,
        )  # fmt: skip
        return result.output
    raise AssertionError("unreachable")  # pragma: no cover


async def suggest_tags(
    llm: LLMProvider, snippet: Snippet, usage: AiUsageService
) -> SnippetTagSuggestion:
    messages = [
        Message("system", load(TAGS_PROMPT)),
        Message(
            "user",
            f"Title: {_clean(snippet.title)}\n"
            f"Description: {_clean(snippet.description or '')}\n\n{_clean(snippet.code)}",
        ),
    ]
    return await structured_call(
        llm, messages, SnippetTagSuggestion, feature="auto_tag",
        prompt_version=TAGS_PROMPT, usage=usage, max_output_tokens=300,
    )  # fmt: skip


# ---- explain an HTTP error (the API tester) ----

HTTP_ERROR_PROMPT = "explain_http_error_v1"
BODY_EXCERPT = 2_000
# Headers that help diagnose a failure; the rest (cookies, tracking) would only add noise.
USEFUL_HEADERS = {"content-type", "www-authenticate", "retry-after", "allow", "location",
                  "x-ratelimit-remaining", "x-ratelimit-reset", "ratelimit-remaining",
                  "access-control-allow-origin", "server"}  # fmt: skip


async def explain_http_error(
    llm: LLMProvider, request: ExplainErrorRequest, usage: AiUsageService
) -> HttpErrorExplanation:
    url = urlsplit(request.url)
    # The query string can carry tokens (?api_key=...); the path is enough to reason with.
    shown_url = urlunsplit((url.scheme, url.netloc, url.path, "", ""))
    headers = "\n".join(
        f"{name}: {_clean(value)}"
        for name, value in request.response_headers
        if name.lower() in USEFUL_HEADERS
    )
    body = _clean(request.response_body[:BODY_EXCERPT])
    messages = [
        Message("system", load(HTTP_ERROR_PROMPT)),
        Message(
            "user",
            f"Request: {request.method} {shown_url}\n"
            f"Response: {request.status} {request.status_text}\n"
            f"Headers:\n{headers or '(none)'}\n\nBody (start):\n{body or '(empty)'}",
        ),
    ]
    return await structured_call(
        llm, messages, HttpErrorExplanation, feature="explain_http_error",
        prompt_version=HTTP_ERROR_PROMPT, usage=usage,
    )  # fmt: skip


# ---- ask your notes ----


async def retrieve(
    session: AsyncSession,
    user_id: UUID,
    question: str,
    embeddings: EmbeddingProvider,
    min_similarity: float,
) -> list[ChunkHit]:
    """The passages to answer from — or none, when nothing is close enough in meaning.

    The guardrail: keyword hits alone ("password" appears somewhere) don't justify an
    answer. With no passage semantically close to the question, the answer is "not found"
    and the LLM is never called — no cost, and no confident answer invented from nothing.
    """
    vector = await embeddings.embed_query(question)
    hits = await search_chunks(
        session, user_id, q=question, vector=vector,
        max_distance=1 - min_similarity, limit=MAX_SOURCES,
    )  # fmt: skip
    return hits if any(hit.similarity is not None for hit in hits) else []


def sources_for(hits: list[ChunkHit]) -> list[Source]:
    return [
        Source(
            n=n,
            note_id=hit.chunk.note_id,
            note_title=hit.note_title or "Untitled",
            heading=hit.chunk.heading,
            excerpt=hit.chunk.content[:240],
        )
        for n, hit in enumerate(hits, start=1)
    ]


def ask_messages(question: str, hits: list[ChunkHit]) -> list[Message]:
    blocks = []
    for n, hit in enumerate(hits, start=1):
        where = " — ".join(
            part for part in (hit.note_title or "Untitled", hit.chunk.heading) if part
        )
        blocks.append(f"[{n}] ({where})\n{_clean(hit.chunk.content)}")
    return [
        Message("system", load(ASK_PROMPT)),
        Message("user", "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {_clean(question)}"),
    ]


async def not_found_answer() -> AsyncIterator[str]:
    yield sse("sources", [])
    yield sse("token", {"text": NOT_FOUND})
    yield sse("done", {"usage": {"input_tokens": 0, "output_tokens": 0}, "latency_ms": 0})
