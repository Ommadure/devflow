"""Versioned prompt templates. A prompt is code: changing one is a new file and a new
version, and every LLM call logs the version it used, so a quality change can be traced
to the prompt change that caused it."""

from functools import cache
from pathlib import Path

PROMPTS = Path(__file__).parent


@cache
def load(name: str) -> str:
    """load("explain_code_v1") → the template text."""
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
