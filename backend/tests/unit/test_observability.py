from typing import Any, cast

from sentry_sdk.types import Event

from app.core.config import Settings
from app.core.logging import new_context
from app.core.observability import init_sentry, scrub_event


def test_sentry_stays_off_without_a_dsn(settings: Settings) -> None:
    assert init_sentry(settings, component="api") is False


def test_scrub_removes_credentials_and_bodies_but_keeps_context() -> None:
    new_context(request_id="req-1", user_id="user-1")
    event = cast(
        Event,
        {
            "request": {
                "url": "https://api.test/api/v1/auth/login",
                "data": {"password": "Correct-Horse-9"},
                "cookies": {"devflow_refresh": "secret"},
                "query_string": "token=secret",
                "headers": {
                    "Authorization": "Bearer secret",
                    "Cookie": "devflow_refresh=secret",
                    "User-Agent": "pytest",
                },
            }
        },
    )
    scrubbed = scrub_event(event, {})
    assert scrubbed is not None
    request = cast(dict[str, Any], scrubbed["request"])
    assert set(request) == {"url", "headers"}
    assert request["headers"] == {"User-Agent": "pytest"}
    assert "secret" not in str(scrubbed)
    assert scrubbed["tags"] == {"request_id": "req-1", "user_id": "user-1"}
