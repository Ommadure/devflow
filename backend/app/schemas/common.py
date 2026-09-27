"""Reusable field types for request models."""

from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints

# Titles are trimmed; an all-spaces title counts as empty.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def normalize_tags(tags: list[str]) -> list[str]:
    """Lowercase, trim, spaces to dashes, drop blanks and duplicates (order kept):
    ["React Hooks", "react-hooks", " "] → ["react-hooks"]."""
    seen: dict[str, None] = {}
    for tag in tags:
        cleaned = "-".join(tag.strip().lower().split())
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen)


def _lowercase(value: str | None) -> str | None:
    return value.lower() if value else value


# "Python", " python " and "" → "python", "python", None.
Language = Annotated[
    Annotated[str, StringConstraints(max_length=40)] | None,
    AfterValidator(blank_to_none),
    AfterValidator(_lowercase),
]
Tags = Annotated[
    list[Annotated[str, StringConstraints(max_length=40)]],
    Field(max_length=20),
    AfterValidator(normalize_tags),
]
