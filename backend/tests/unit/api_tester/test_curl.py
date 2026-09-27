import base64

import pytest

from app.core.errors import ValidationFailedError
from app.services.api_tester.curl import parse_curl


def test_a_get() -> None:
    parsed = parse_curl("curl https://api.example.com/users")
    assert (parsed.method, parsed.url, parsed.headers, parsed.body) == (
        "GET", "https://api.example.com/users", {}, None,
    )  # fmt: skip


def test_devtools_style_multiline_with_quotes_headers_and_json() -> None:
    parsed = parse_curl(
        """curl 'https://api.example.com/items?q=a%20b' \\
  -X POST \\
  -H 'Authorization: Bearer abc.def' \\
  -H "X-Note: it's quoted" \\
  --data-raw '{"name": "Widget", "tags": ["a", "b"]}'"""
    )
    assert parsed.method == "POST"
    assert parsed.url == "https://api.example.com/items?q=a%20b"
    assert parsed.headers["Authorization"] == "Bearer abc.def"
    assert parsed.headers["X-Note"] == "it's quoted"
    assert parsed.headers["Content-Type"] == "application/json"
    assert parsed.body == '{"name": "Widget", "tags": ["a", "b"]}'


def test_data_implies_post_and_several_data_flags_join_like_curl() -> None:
    parsed = parse_curl("curl -d a=1 -d b=2 https://x.example")
    assert (parsed.method, parsed.body) == ("POST", "a=1&b=2")
    assert parsed.headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_json_flag_sets_both_headers() -> None:
    parsed = parse_curl("""curl --json '{"a":1}' https://x.example""")
    assert parsed.method == "POST"
    assert parsed.headers["Content-Type"] == parsed.headers["Accept"] == "application/json"


def test_user_becomes_a_basic_auth_header() -> None:
    parsed = parse_curl("curl -u alice:s3cret https://x.example")
    assert parsed.headers["Authorization"] == "Basic " + base64.b64encode(b"alice:s3cret").decode()


def test_equals_syntax_head_and_ignored_flags() -> None:
    parsed = parse_curl(
        "curl -sSL --compressed --max-time 5 --request=DELETE --url=https://x.example/1"
    )
    assert (parsed.method, parsed.url, parsed.warnings) == ("DELETE", "https://x.example/1", [])
    assert parse_curl("curl -I https://x.example").method == "HEAD"
    glued = parse_curl("curl -XPUT -H'Accept: text/plain' https://x.example")
    assert (glued.method, glued.headers) == ("PUT", {"Accept": "text/plain"})


def test_unknown_flags_and_file_data_are_reported_not_dropped() -> None:
    parsed = parse_curl("curl --cert me.pem -d @body.json https://x.example")
    assert "--cert" in parsed.warnings[0]
    assert any("@file" in warning for warning in parsed.warnings)


@pytest.mark.parametrize(
    "command",
    ["wget https://x.example", "curl -H", "curl 'unclosed https://x.example", "curl -X POST"],
)
def test_invalid_commands_explain_themselves(command: str) -> None:
    with pytest.raises(ValidationFailedError) as caught:
        parse_curl(command)
    assert caught.value.code == "INVALID_CURL"
