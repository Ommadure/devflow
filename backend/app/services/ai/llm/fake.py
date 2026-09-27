"""Scripted LLM for tests (and running without an API key). Never touches the network."""

import re
from collections.abc import AsyncGenerator, Callable, Sequence

from app.services.ai.llm.base import (
    Completion,
    LLMError,
    LLMProvider,
    Message,
    StreamChunk,
    TokenUsage,
)

Response = str | Exception
Responder = Callable[[list[Message]], Response]
DEFAULT_ANSWER = "(fake model) This is a canned answer: set LLM_PROVIDER=gemini for real ones."


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)  # ~4 characters per token in English


class FakeLLMProvider(LLMProvider):
    """Answers from a script (in call order), a responder function, or a default.

    Script items can be text (valid JSON, broken JSON, anything) or an exception to raise,
    so tests can drive every failure path. `fail_stream_after` raises mid-stream after
    that many chunks, to test errors that arrive after the answer has started.
    """

    name = "fake"

    def __init__(
        self,
        script: Sequence[Response] = (),
        *,
        responder: Responder | None = None,
        default: Response = DEFAULT_ANSWER,
        model: str = "fake-model",
        fail_stream_after: int | None = None,
    ) -> None:
        self.model = model
        self._script = list(script)
        self._responder = responder
        self._default = default
        self._fail_stream_after = fail_stream_after
        self.calls: list[list[Message]] = []

    def _next(self, messages: list[Message]) -> str:
        self.calls.append(messages)
        if self._script:
            response = self._script.pop(0)
        elif self._responder:
            response = self._responder(messages)
        else:
            response = self._default
        if isinstance(response, Exception):
            raise response
        return response

    def _usage(self, messages: list[Message], answer: str) -> TokenUsage:
        prompt = "\n".join(message.content for message in messages)
        return TokenUsage(estimate_tokens(prompt), estimate_tokens(answer))

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float,
        json_output: bool = False,
        max_output_tokens: int | None = None,
    ) -> Completion:
        answer = self._next(messages)
        return Completion(answer, self._usage(messages, answer), latency_ms=1, model=self.model)

    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float,
        max_output_tokens: int | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        answer = self._next(messages)
        # Word-sized chunks, keeping the spaces: joined back together they equal `answer`.
        for index, piece in enumerate(re.findall(r"\S+\s*|\s+", answer)):
            if self._fail_stream_after is not None and index >= self._fail_stream_after:
                raise LLMError("fake stream failure", usage=TokenUsage(1, index))
            yield StreamChunk(text=piece)
        yield StreamChunk(usage=self._usage(messages, answer))
