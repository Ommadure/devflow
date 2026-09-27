"""One LLM provider per process, built from settings."""

from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings
from app.services.ai.llm.base import LLMProvider
from app.services.ai.llm.fake import FakeLLMProvider
from app.services.ai.llm.gemini import GeminiProvider


def check_llm_config(settings: Settings) -> None:
    """Checked when the API or worker starts — not in Settings, which migrations and scripts
    also load, and they have no business needing an LLM key."""
    if settings.llm_provider == "gemini" and not settings.gemini_api_key.get_secret_value():
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to backend/.env, or set LLM_PROVIDER=fake "
            "to run with canned answers."
        )


@lru_cache
def llm_http_client() -> httpx.AsyncClient:
    # One pooled client: connections to the provider are reused across requests.
    return httpx.AsyncClient(timeout=get_settings().llm_timeout_seconds)


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "fake":
        return FakeLLMProvider(model=settings.llm_model or "fake-model")
    return GeminiProvider(
        settings.gemini_api_key.get_secret_value(),
        settings.llm_model,
        llm_http_client(),
        timeout=settings.llm_timeout_seconds,
        thinking_level=settings.llm_thinking_level,
    )
