import pytest

from app.services.ai.redaction import REDACTED, redact

# Assembled from parts so no real-looking secret sits whole in the repository.
AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
GITHUB = "ghp_" + "a" * 36
STRIPE = "sk_live_" + "b" * 24
GOOGLE = "AIza" + "c" * 35
SLACK = "xoxb-" + "1234567890-abcdef"
JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + ".eyJ" + "zdWIiOiIxMjM0In0" + "." + "d" * 20


@pytest.mark.parametrize(
    ("text", "secret", "kind"),
    [
        (f"aws = {AWS}", AWS, "AWS access key ID"),
        (f"token: {GITHUB}", GITHUB, "GitHub token"),
        (f"stripe.api_key = {STRIPE}", STRIPE, "Stripe key"),
        (f"key={GOOGLE}", GOOGLE, "Google API key"),
        (f"SLACK={SLACK}", SLACK, "Slack token"),
        (f"Authorization: Bearer {JWT}", JWT, "JSON Web Token"),
        ('API_KEY = "hunter2hunter2"', "hunter2hunter2", "hardcoded credential"),
        ('{"password": "s3cr3t-pa55"}', "s3cr3t-pa55", "hardcoded credential"),
    ],
)
def test_each_pattern_is_redacted(text: str, secret: str, kind: str) -> None:
    redacted, kinds = redact(text)
    assert secret not in redacted
    assert REDACTED in redacted
    assert kind in kinds


def test_private_key_blocks_are_removed_whole() -> None:
    text = "key:\n-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nabc\n-----END RSA PRIVATE KEY-----\ndone"
    redacted, kinds = redact(text)
    assert "MIIEow" not in redacted and "BEGIN" not in redacted
    assert redacted == f"key:\n{REDACTED}\ndone"
    assert kinds == ["private key"]


def test_an_unterminated_private_key_is_still_removed() -> None:
    redacted, _ = redact("-----BEGIN PRIVATE KEY-----\nMIIEow...")
    assert "MIIEow" not in redacted


def test_placeholders_and_ordinary_code_are_left_alone() -> None:
    for text in (
        'API_KEY = "your-api-key-here"',
        'password = "${PASSWORD}"',
        "const token = getToken();",
        "def verify(password: str) -> bool:",
    ):
        assert redact(text) == (text, [])


def test_redaction_keeps_the_surrounding_code() -> None:
    redacted, _ = redact('client = Stripe(api_key="sk_live_' + "x" * 24 + '")')
    assert redacted == f'client = Stripe(api_key="{REDACTED}")'
