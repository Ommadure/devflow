import pytest
from pydantic import BaseModel

from app.schemas.ai import SnippetTagSuggestion
from app.services.ai.llm.base import TokenUsage, parse_json_output
from app.services.ai.pricing import cost_usd


class Pair(BaseModel):
    a: int
    b: str


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1, "b": "x"}',
        '```json\n{"a": 1, "b": "x"}\n```',
        'Sure! {"a": 1, "b": "x"} Hope it helps.',
    ],
)
def test_json_is_found_inside_common_wrappings(text: str) -> None:
    assert parse_json_output(text, Pair) == Pair(a=1, b="x")


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("no json here", "no JSON object"),
        ('{"a": 1,', "malformed JSON"),
        ('{"a": "x", "b": "y"}', "schema mismatch"),
    ],
)
def test_bad_output_says_what_is_wrong(text: str, problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        parse_json_output(text, Pair)


def test_tag_suggestions_are_normalised() -> None:
    suggestion = SnippetTagSuggestion.model_validate(
        {
            "language": " TypeScript ",
            "tags": ["React Hooks", "react-hooks", "Timing", "a", "b", "c", "d"],
            "description": "Delays a value.",
        }
    )
    assert suggestion.language == "typescript"
    assert suggestion.tags == ["react-hooks", "timing", "a", "b", "c"]


def test_cost_uses_configured_prices_including_versioned_names() -> None:
    prices = {"gemini-3.5-flash": (0.30, 2.50)}
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=200_000)
    assert cost_usd("gemini-3.5-flash", usage, prices) == pytest.approx(0.80)
    assert cost_usd("gemini-3.5-flash-001", usage, prices) == pytest.approx(0.80)
    assert cost_usd("unpriced-model", usage, prices) == 0.0
