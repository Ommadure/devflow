"""The Gemini client against recorded-shape responses (respx): no network, no API bill."""

import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from app.services.ai.llm.base import LLMError, LLMRateLimited, Message, StreamChunk
from app.services.ai.llm.gemini import GEMINI_API_URL, GeminiProvider

MODEL = "gemini-test"
MESSAGES = [Message("system", "be brief"), Message("user", "hi")]


async def no_sleep(_: float) -> None:
    return None


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


def provider(http: httpx.AsyncClient) -> GeminiProvider:
    return GeminiProvider("test-key", MODEL, http, sleep=no_sleep)


def answer(text: str, *, prompt: int = 10, output: int = 5, thoughts: int = 0) -> dict[str, object]:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {
            "promptTokenCount": prompt,
            "candidatesTokenCount": output,
            "thoughtsTokenCount": thoughts,
        },
        "modelVersion": f"{MODEL}-001",
    }


def sse_body(*events: dict[str, object]) -> str:
    return "".join(f"data: {json.dumps(event)}\r\n\r\n" for event in events)


@respx.mock
async def test_complete_sends_the_key_in_a_header_and_counts_thinking_tokens(
    http: httpx.AsyncClient,
) -> None:
    route = respx.post(f"{GEMINI_API_URL}/models/{MODEL}:generateContent").respond(
        json=answer("hello", thoughts=7)
    )
    completion = await provider(http).complete(MESSAGES, temperature=0.2, json_output=True)

    request = route.calls.last.request
    assert request.headers["x-goog-api-key"] == "test-key"
    assert "test-key" not in str(request.url)  # never in the URL (access logs)
    body = json.loads(request.content)
    assert body["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert (completion.text, completion.usage.output_tokens, completion.model) == (
        "hello",
        12,
        f"{MODEL}-001",
    )


@respx.mock
async def test_complete_retries_a_503_then_succeeds(http: httpx.AsyncClient) -> None:
    respx.post(f"{GEMINI_API_URL}/models/{MODEL}:generateContent").mock(
        side_effect=[httpx.Response(503, json={"error": {"message": "high demand"}}),
                     httpx.Response(200, json=answer("ok"))]
    )  # fmt: skip
    assert (await provider(http).complete(MESSAGES, temperature=0.2)).text == "ok"


@respx.mock
async def test_a_long_rate_limit_is_raised_not_waited_out(http: httpx.AsyncClient) -> None:
    respx.post(f"{GEMINI_API_URL}/models/{MODEL}:generateContent").respond(
        429, headers={"Retry-After": "90"}, json={"error": {"message": "quota"}}
    )
    with pytest.raises(LLMRateLimited) as caught:
        await provider(http).complete(MESSAGES, temperature=0.2)
    assert caught.value.retry_after == 90


@respx.mock
async def test_a_blocked_prompt_is_an_error(http: httpx.AsyncClient) -> None:
    respx.post(f"{GEMINI_API_URL}/models/{MODEL}:generateContent").respond(
        json={"promptFeedback": {"blockReason": "SAFETY"}}
    )
    with pytest.raises(LLMError, match="SAFETY"):
        await provider(http).complete(MESSAGES, temperature=0.2)


@respx.mock
async def test_stream_yields_text_then_the_final_usage(http: httpx.AsyncClient) -> None:
    route = respx.post(f"{GEMINI_API_URL}/models/{MODEL}:streamGenerateContent").respond(
        text=sse_body(
            {"candidates": [{"content": {"parts": [{"text": "Hel"}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "lo"}]}}]},
            answer("!", prompt=12, output=3),
        ),
        headers={"content-type": "text/event-stream"},
    )
    chunks: list[StreamChunk] = [
        chunk async for chunk in provider(http).stream(MESSAGES, temperature=0.3)
    ]

    assert route.calls.last.request.url.params["alt"] == "sse"
    assert "".join(chunk.text for chunk in chunks) == "Hello!"
    assert chunks[-1].usage is not None
    assert (chunks[-1].usage.input_tokens, chunks[-1].usage.output_tokens) == (12, 3)


@respx.mock
async def test_stream_retries_before_the_first_token(http: httpx.AsyncClient) -> None:
    respx.post(f"{GEMINI_API_URL}/models/{MODEL}:streamGenerateContent").mock(
        side_effect=[httpx.Response(503, json={"error": {"message": "busy"}}),
                     httpx.Response(200, text=sse_body(answer("ok")))]
    )  # fmt: skip
    text = "".join([c.text async for c in provider(http).stream(MESSAGES, temperature=0.3)])
    assert text == "ok"


@respx.mock
async def test_stream_error_status_raises(http: httpx.AsyncClient) -> None:
    respx.post(f"{GEMINI_API_URL}/models/{MODEL}:streamGenerateContent").respond(
        400, json={"error": {"message": "bad request"}}
    )
    with pytest.raises(LLMError, match="bad request"):
        _ = [c async for c in provider(http).stream(MESSAGES, temperature=0.3)]


def test_model_names_are_validated(http: httpx.AsyncClient) -> None:
    with pytest.raises(ValueError, match="invalid model"):
        GeminiProvider("k", "../../evil", http)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiProvider("", MODEL, http)
