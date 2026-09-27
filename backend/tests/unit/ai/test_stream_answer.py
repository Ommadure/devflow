"""stream_answer's promises: SSE framing, and a usage record whatever happens —
including the client disconnecting halfway through. Deterministic: no timing sleeps."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, cast

from app.services.ai.assistant import sse, stream_answer
from app.services.ai.llm.base import Message, StreamChunk
from app.services.ai.llm.fake import FakeLLMProvider
from app.services.ai.usage import AiUsageService


class RecordingUsage:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record(self, feature: str, **fields: Any) -> None:
        await asyncio.sleep(0)  # a real await, as a database write would be
        self.records.append({"feature": feature, **fields})


MESSAGES = [Message("user", "hi")]


def answer(llm: FakeLLMProvider, usage: RecordingUsage, **kwargs: Any) -> AsyncGenerator[str, None]:
    return stream_answer(
        llm, MESSAGES, feature="explain_code", prompt_version="v1",
        usage=cast(AiUsageService, usage), **kwargs,
    )  # fmt: skip


def test_sse_framing() -> None:
    assert sse("token", {"text": "a\nb"}) == 'event: token\ndata: {"text": "a\\nb"}\n\n'


async def test_a_disconnect_between_tokens_is_recorded() -> None:
    """Closed while paused at a `yield`, waiting for the last token to be sent (GeneratorExit)."""
    usage = RecordingUsage()
    events = answer(FakeLLMProvider(default="one two three four"), usage)
    await anext(events)
    await anext(events)
    await events.aclose()  # what happens when the connection drops between sends

    [record] = usage.records
    assert (record["status"], record["error_code"]) == ("error", "CLIENT_DISCONNECTED")


async def test_a_disconnect_while_waiting_on_the_model_is_recorded() -> None:
    """Cancelled while awaiting the model's next token (CancelledError)."""
    waiting_for_model = asyncio.Event()

    class SlowModel(FakeLLMProvider):
        async def stream(self, *args: Any, **kwargs: Any) -> AsyncGenerator[StreamChunk, None]:
            async for chunk in super().stream(*args, **kwargs):
                yield chunk
                waiting_for_model.set()
                await asyncio.Event().wait()  # the next token never comes

    usage = RecordingUsage()
    events = answer(SlowModel(default="a b c"), usage)
    await anext(events)
    pending = asyncio.create_task(anext(events))
    await waiting_for_model.wait()  # deterministic: the generator is now inside the model
    pending.cancel()  # what Starlette does when the connection drops
    await asyncio.gather(pending, return_exceptions=True)

    [record] = usage.records
    assert (record["status"], record["error_code"]) == ("error", "CLIENT_DISCONNECTED")


async def test_before_events_come_first_and_success_is_recorded() -> None:
    usage = RecordingUsage()
    events = [
        e async for e in answer(FakeLLMProvider(default="ok"), usage, before=[sse("sources", [])])
    ]
    assert events[0] == sse("sources", [])
    assert events[-1].startswith("event: done")
    assert usage.records[0]["status"] == "success"
