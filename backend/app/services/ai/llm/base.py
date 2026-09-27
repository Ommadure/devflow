"""The LLM seam: everything the app knows about language models.

A provider implements two methods: `complete()` (messages in, the whole text out) and
`stream()` (the same, token chunks as they arrive). Structured output is built once, on
top of `complete()`: parse the JSON, validate it with Pydantic — vendor JSON modes help,
but are never trusted on their own. Ported from ReviewPilot, plus streaming.
"""

import json
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ValidationError

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Completion:
    text: str
    usage: TokenUsage
    latency_ms: int
    model: str


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    output: T
    usage: TokenUsage
    latency_ms: int
    model: str


@dataclass(frozen=True)
class StreamChunk:
    """A piece of the answer. The last chunk of a stream carries the final usage."""

    text: str = ""
    usage: TokenUsage | None = None


class LLMError(Exception):
    """A call failed. `usage` is set when tokens were still spent (and billed)."""

    code = "LLM_ERROR"

    def __init__(
        self, message: str, *, usage: TokenUsage | None = None, latency_ms: int = 0
    ) -> None:
        super().__init__(message)
        self.usage = usage or TokenUsage()
        self.latency_ms = latency_ms


class LLMRateLimited(LLMError):
    code = "LLM_RATE_LIMITED"

    def __init__(self, message: str, *, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMInvalidOutput(LLMError):
    """The model answered, but not with JSON matching the schema."""

    code = "LLM_INVALID_OUTPUT"

    def __init__(self, problem: str, *, raw_text: str, usage: TokenUsage, latency_ms: int) -> None:
        super().__init__(f"invalid output: {problem}", usage=usage, latency_ms=latency_ms)
        self.problem = problem
        self.raw_text = raw_text


class LLMProvider(ABC):
    name: str = "base"
    model: str

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float,
        json_output: bool = False,
        max_output_tokens: int | None = None,
    ) -> Completion: ...

    @abstractmethod
    def stream(
        self,
        messages: list[Message],
        *,
        temperature: float,
        max_output_tokens: int | None = None,
    ) -> AsyncGenerator[StreamChunk, None]: ...

    async def generate_structured[T: BaseModel](
        self,
        messages: list[Message],
        schema: type[T],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> LLMResult[T]:
        completion = await self.complete(
            messages,
            temperature=temperature,
            json_output=True,
            max_output_tokens=max_output_tokens,
        )
        try:
            output = parse_json_output(completion.text, schema)
        except ValueError as exc:
            raise LLMInvalidOutput(
                str(exc),
                raw_text=completion.text,
                usage=completion.usage,
                latency_ms=completion.latency_ms,
            ) from exc
        return LLMResult(output, completion.usage, completion.latency_ms, completion.model)


FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def parse_json_output[T: BaseModel](text: str, schema: type[T]) -> T:
    """Lenient about wrapping (code fences, stray prose), strict about content."""
    candidate = text.strip()
    fenced = FENCE.match(candidate)
    if fenced:
        candidate = fenced.group(1)
    if not candidate.startswith("{"):
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("response contains no JSON object")
        candidate = candidate[start : end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON ({exc.msg} at line {exc.lineno})") from exc
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
            for error in exc.errors()[:10]
        )
        raise ValueError(f"schema mismatch: {problems}") from exc
