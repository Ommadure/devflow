"""Token usage → US dollars, from configured prices (LLM_PRICING).

Prices change and differ by tier, so none are hard-coded here: they come from the provider's
pricing page via configuration. An unpriced model costs 0 — visible in `ai_usage` as a
zero cost rather than silently wrong.
"""

from collections.abc import Mapping, Sequence

from app.services.ai.llm.base import TokenUsage

PER_MILLION = 1_000_000


def cost_usd(model: str, usage: TokenUsage, prices: Mapping[str, Sequence[float]]) -> float:
    price = prices.get(model)
    if price is None:
        # Providers report versioned names ("model-001") for an alias ("model").
        matches = [name for name in prices if model.startswith(name)]
        price = prices[max(matches, key=len)] if matches else None
    if price is None:
        return 0.0
    return (usage.input_tokens * price[0] + usage.output_tokens * price[1]) / PER_MILLION
