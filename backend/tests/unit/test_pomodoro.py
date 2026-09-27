from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.errors import ValidationFailedError
from app.services.pomodoro import parse_timezone, start_of_today


def test_today_starts_at_local_midnight() -> None:
    # 20:00 UTC on the 26th is already 01:30 on the 27th in India.
    now = datetime(2026, 9, 26, 20, 0, tzinfo=UTC)
    start = start_of_today(ZoneInfo("Asia/Kolkata"), now)
    assert start.isoformat() == "2026-09-27T00:00:00+05:30"
    assert start.astimezone(UTC) == datetime(2026, 9, 26, 18, 30, tzinfo=UTC)


def test_same_instant_is_still_the_26th_in_new_york() -> None:
    now = datetime(2026, 9, 26, 20, 0, tzinfo=UTC)
    assert start_of_today(ZoneInfo("America/New_York"), now).day == 26


@pytest.mark.parametrize("name", ["Mars/Olympus", "", "../../etc/passwd"])
def test_unknown_timezones_are_rejected(name: str) -> None:
    with pytest.raises(ValidationFailedError):
        parse_timezone(name)
