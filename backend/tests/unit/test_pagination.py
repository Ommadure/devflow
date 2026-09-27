from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.errors import ValidationFailedError
from app.core.pagination import Cursor
from app.repositories._text import like_pattern


def test_cursor_round_trips_exactly() -> None:
    cursor = Cursor(at=datetime(2026, 9, 27, 10, 30, 0, 123456, tzinfo=UTC), id=uuid4())
    assert Cursor.decode(cursor.encode()) == cursor


def test_cursor_is_url_safe() -> None:
    encoded = Cursor(at=datetime.now(UTC), id=uuid4()).encode()
    assert all(c.isalnum() or c in "-_" for c in encoded)


@pytest.mark.parametrize("garbage", ["", "abc", "!!!", "eyJmb28iOiAxfQ"])  # last: {"foo": 1}
def test_bad_cursors_are_a_validation_error(garbage: str) -> None:
    with pytest.raises(ValidationFailedError) as caught:
        Cursor.decode(garbage)
    assert caught.value.code == "INVALID_CURSOR"


@pytest.mark.parametrize(
    ("query", "pattern"),
    [
        ("debounce", "%debounce%"),
        ("100%", "%100\\%%"),
        ("snake_case", "%snake\\_case%"),
        ("C:\\path", "%C:\\\\path%"),
    ],
)
def test_like_patterns_match_wildcards_literally(query: str, pattern: str) -> None:
    assert like_pattern(query) == pattern
