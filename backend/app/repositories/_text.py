"""Helpers for text filters."""


def like_pattern(query: str) -> str:
    """`%query%` for ILIKE, with the user's own `%`, `_` and `\\` matched literally.

    Without escaping, searching for "100%" or "snake_case" would treat those characters
    as wildcards.
    """
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
