"""Replace likely secrets with [REDACTED] before any text leaves for an LLM (spec §8.9).

Snippets are exactly where people paste `API_KEY = "sk_live_..."` to remember it. The LLM
provider logs prompts, may train on them, and is a third party: a secret sent there has
leaked. Patterns are ported from ReviewPilot; each one is unit-tested.
"""

import re
from dataclasses import dataclass

REDACTED = "[REDACTED]"


@dataclass(frozen=True)
class SecretPattern:
    kind: str
    regex: re.Pattern[str]
    group: int = 0  # which group holds the secret (0 = the whole match)


SECRET_PATTERNS: tuple[SecretPattern, ...] = (
    SecretPattern("AWS access key ID", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    SecretPattern("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    SecretPattern("GitHub token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    SecretPattern("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    SecretPattern("Stripe key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    SecretPattern("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    SecretPattern(
        "JSON Web Token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ),
    SecretPattern(
        "hardcoded credential",
        # api_key = "....", "password": "....", SECRET_TOKEN='....' (string literals only)
        re.compile(
            r"(?i)(?:api[_-]?key|secret|token|password|passwd)[\w-]*[\"']?\s*[:=]\s*"
            r"[\"']([^\"'\s]{8,})[\"']"
        ),
        group=1,
    ),
)
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)",
    re.DOTALL,
)
# Values that are obviously not real credentials.
PLACEHOLDER = re.compile(
    r"(?i)(example|placeholder|dummy|changeme|change_me|your[_-]|xxxx|\*\*\*\*|<|\$\{|\{\{)"
)


def redact(text: str) -> tuple[str, list[str]]:
    """Return the text with secrets replaced, and the kinds found (for logs; never values)."""
    kinds: list[str] = []

    def private_key(_: re.Match[str]) -> str:
        kinds.append("private key")
        return REDACTED

    text = PRIVATE_KEY_BLOCK.sub(private_key, text)
    for pattern in SECRET_PATTERNS:

        def substitute(match: re.Match[str], pattern: SecretPattern = pattern) -> str:
            secret = match.group(pattern.group)
            if REDACTED in secret or (pattern.group and PLACEHOLDER.search(secret)):
                return match.group(0)
            kinds.append(pattern.kind)
            start = match.start(pattern.group) - match.start(0)
            whole = match.group(0)
            return whole[:start] + REDACTED + whole[start + len(secret) :]

        text = pattern.regex.sub(substitute, text)
    return text, kinds
