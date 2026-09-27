"""Google Gemini via its REST API: generateContent, and streamGenerateContent for SSE.

Plain httpx instead of the Google SDK: one less dependency, and respx mocks it in tests.
Reference: https://ai.google.dev/api/generate-content
"""

import asyncio
import json
import random
import re
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

import httpx
import structlog

from app.services.ai.llm.base import (
    Completion,
    LLMError,
    LLMProvider,
    LLMRateLimited,
    Message,
    StreamChunk,
    TokenUsage,
)

log = structlog.get_logger()
Sleep = Callable[[float], Awaitable[None]]
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DURATION = re.compile(r"^(\d+(?:\.\d+)?)s$")


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        http: httpx.AsyncClient,
        *,
        base_url: str = GEMINI_API_URL,
        timeout: float = 60.0,
        max_retries: int = 2,
        max_inline_wait: float = 10.0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        if not MODEL_NAME.fullmatch(model):
            raise ValueError(f"invalid model name {model!r}")
        self.model = model
        self._api_key = api_key
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_inline_wait = max_inline_wait
        self._sleep = sleep

    @property
    def _headers(self) -> dict[str, str]:
        # The key goes in a header, never the URL, so it can't end up in access logs.
        return {"x-goog-api-key": self._api_key}

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float,
        json_output: bool = False,
        max_output_tokens: int | None = None,
    ) -> Completion:
        url = f"{self._base_url}/models/{self.model}:generateContent"
        body = _request_body(messages, temperature, max_output_tokens, json_output=json_output)
        started = time.monotonic()
        attempt = 0
        while True:
            try:
                response = await self._http.post(
                    url, json=body, headers=self._headers, timeout=self._timeout
                )
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    raise LLMError(
                        f"Gemini unreachable: {type(exc).__name__}", latency_ms=_since(started)
                    ) from exc
                await self._retry(_backoff(attempt), attempt, type(exc).__name__)
                attempt += 1
                continue
            if await self._should_retry(response, attempt):
                attempt += 1
                continue
            _raise_for_error(response, started)
            return _parse_completion(response.json(), self.model, _since(started))

    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float,
        max_output_tokens: int | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Yield text as Gemini produces it, then one final chunk with the usage.

        Retries happen only before the first token: once text has reached the user, a
        retry would repeat it. Closing this generator (the client went away) closes the
        HTTP stream, which cancels the upstream generation — and its billing.
        """
        url = f"{self._base_url}/models/{self.model}:streamGenerateContent"
        body = _request_body(messages, temperature, max_output_tokens, json_output=False)
        started = time.monotonic()
        attempt = 0
        while True:
            try:
                async with self._http.stream(
                    "POST",
                    url,
                    params={"alt": "sse"},
                    json=body,
                    headers=self._headers,
                    timeout=self._timeout,
                ) as response:
                    if response.is_error:
                        await response.aread()
                        if await self._should_retry(response, attempt):
                            attempt += 1
                            continue
                        _raise_for_error(response, started)
                    usage = TokenUsage()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue  # blank separators between SSE events
                        data = json.loads(line.removeprefix("data:").strip())
                        usage = _usage(data) or usage
                        text = _text(data)
                        if text:
                            yield StreamChunk(text=text)
                        elif not data.get("candidates"):
                            _raise_if_blocked(data, usage)
                    yield StreamChunk(usage=usage)
                    return
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    raise LLMError(
                        f"Gemini unreachable: {type(exc).__name__}", latency_ms=_since(started)
                    ) from exc
                await self._retry(_backoff(attempt), attempt, type(exc).__name__)
                attempt += 1

    async def _should_retry(self, response: httpx.Response, attempt: int) -> bool:
        if response.status_code == 429:
            wait = _retry_delay(response) or _backoff(attempt)
            if wait <= self._max_inline_wait and attempt < self._max_retries:
                await self._retry(wait, attempt, "429 rate limited")
                return True
            raise LLMRateLimited("The AI provider is busy. Try again shortly.", retry_after=wait)
        if response.status_code >= 500 and attempt < self._max_retries:
            await self._retry(_backoff(attempt), attempt, str(response.status_code))
            return True
        return False

    async def _retry(self, wait: float, attempt: int, reason: str) -> None:
        log.warning(
            "llm.retry", provider=self.name, model=self.model, attempt=attempt + 1,
            reason=reason, wait_s=round(wait, 1),
        )  # fmt: skip
        await self._sleep(wait)


def _since(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _request_body(
    messages: list[Message],
    temperature: float,
    max_output_tokens: int | None,
    *,
    json_output: bool,
) -> dict[str, Any]:
    system = "\n\n".join(m.content for m in messages if m.role == "system")
    contents = [
        {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
        for m in messages
        if m.role != "system"
    ]
    config: dict[str, Any] = {"temperature": temperature}
    if json_output:
        config["responseMimeType"] = "application/json"
    if max_output_tokens:
        # A hard ceiling on what one call can bill (and on a runaway answer).
        config["maxOutputTokens"] = max_output_tokens
    body: dict[str, Any] = {"contents": contents, "generationConfig": config}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return body


def _usage(data: dict[str, Any]) -> TokenUsage | None:
    metadata = data.get("usageMetadata")
    if not metadata:
        return None
    return TokenUsage(
        input_tokens=int(metadata.get("promptTokenCount", 0)),
        # "Thinking" tokens are billed as output tokens.
        output_tokens=int(metadata.get("candidatesTokenCount", 0))
        + int(metadata.get("thoughtsTokenCount", 0)),
    )


def _text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts if not part.get("thought"))


def _raise_if_blocked(data: dict[str, Any], usage: TokenUsage) -> None:
    reason = (data.get("promptFeedback") or {}).get("blockReason")
    if reason:
        raise LLMError(f"Gemini declined to answer (blockReason={reason})", usage=usage)


def _parse_completion(data: dict[str, Any], model: str, latency_ms: int) -> Completion:
    usage = _usage(data) or TokenUsage()
    if not data.get("candidates"):
        _raise_if_blocked(data, usage)
        raise LLMError("Gemini returned no answer", usage=usage)
    return Completion(_text(data), usage, latency_ms, str(data.get("modelVersion") or model))


def _raise_for_error(response: httpx.Response, started: float) -> None:
    if response.is_error:
        raise LLMError(
            f"Gemini {response.status_code}: {_error_message(response)}",
            latency_ms=_since(started),
        )


def _retry_delay(response: httpx.Response) -> float | None:
    if "retry-after" in response.headers:
        try:
            return float(response.headers["retry-after"])
        except ValueError:
            pass
    try:
        details = response.json().get("error", {}).get("details", [])
    except ValueError:
        return None
    for detail in details:
        if str(detail.get("@type", "")).endswith("RetryInfo"):
            match = DURATION.match(str(detail.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    return None


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", {}).get("message", response.text))[:300]
    except ValueError:
        return response.text[:300]


def _backoff(attempt: int) -> float:
    # ~2 s, 4 s (+ jitter): Gemini's "high demand" 503s usually clear within seconds.
    return 2.0 * 2.0**attempt + random.uniform(0, 1)  # noqa: S311 (not crypto)
