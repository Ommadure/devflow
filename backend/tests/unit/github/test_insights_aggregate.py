from datetime import date

import pytest

from app.core.errors import ValidationFailedError
from app.services.github.client import validate_username
from app.services.github.insights import aggregate, last_week_start, week_start

MONDAY = date(2026, 9, 21)


def event(kind: str, when: str, repo: str = "om/devflow", **payload: object) -> dict[str, object]:
    return {"type": kind, "created_at": when, "repo": {"name": repo}, "payload": payload}


def test_counts_only_the_week_in_india_time() -> None:
    events = [
        event("PushEvent", "2026-09-20T19:00:00Z", size=9),  # Mon 00:30 IST: in the week
        event("PushEvent", "2026-09-20T18:00:00Z", size=5),  # Sun 23:30 IST: the week before
        event("PushEvent", "2026-09-22T10:00:00Z", size=2),
        event("PullRequestEvent", "2026-09-23T10:00:00Z", action="opened"),
        event(
            "PullRequestEvent",
            "2026-09-24T10:00:00Z",
            action="closed",
            pull_request={"merged": True},
        ),
        event(
            "PullRequestEvent",
            "2026-09-24T11:00:00Z",
            action="closed",
            pull_request={"merged": False},
        ),
        event("IssuesEvent", "2026-09-25T10:00:00Z", repo="om/other", action="opened"),
        event("PullRequestReviewEvent", "2026-09-25T11:00:00Z"),
        event("PushEvent", "2026-09-27T18:30:00Z", size=1),  # Mon 00:00 IST: next week
    ]
    stats = aggregate(events, MONDAY)
    assert stats["events"] == 7
    assert stats["commits"] == 11
    assert (stats["pull_requests_opened"], stats["pull_requests_merged"]) == (1, 1)
    assert (stats["issues_opened"], stats["reviews"]) == (1, 1)
    assert stats["repositories"][0] == {"name": "om/devflow", "events": 6}
    assert stats["active_days"] == 5


def test_an_empty_week_is_all_zeros() -> None:
    assert aggregate([], MONDAY)["events"] == 0


def test_weeks_start_on_monday() -> None:
    assert week_start(date(2026, 9, 27)) == MONDAY  # a Sunday
    assert week_start(MONDAY) == MONDAY


def test_last_week_is_the_previous_monday_in_india() -> None:
    from datetime import UTC, datetime

    # Monday 00:30 UTC = Monday 06:00 IST: "last week" began a week ago.
    assert last_week_start(datetime(2026, 9, 28, 0, 30, tzinfo=UTC)) == MONDAY


@pytest.mark.parametrize("name", ["octocat", "a", "om-madure", "A1-b2-C3", "x" * 39])
def test_valid_usernames(name: str) -> None:
    assert validate_username(name) == name


@pytest.mark.parametrize(
    "name", ["", "-lead", "trail-", "dou--ble", "x" * 40, "../../orgs", "a/b", "a b", "a?x=1"]
)
def test_invalid_usernames_never_reach_a_url(name: str) -> None:
    with pytest.raises(ValidationFailedError):
        validate_username(name)
