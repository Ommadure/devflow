"""Parse a copied cURL command into a request (spec §11.6: "use AI only where rules can't").

A shell-quoting parser (shlex) plus a table of flags does this exactly, instantly and for
free — an LLM would be slower, cost money, and occasionally invent a header. Flags we
don't model are reported back as warnings, never silently dropped.
"""

import base64
import json
import shlex
from dataclasses import dataclass, field

from app.core.errors import ValidationFailedError

DATA_FLAGS = {"-d", "--data", "--data-raw", "--data-binary", "--data-ascii", "--data-urlencode"}
# Flags that change nothing about the request itself.
IGNORED = {"-s", "--silent", "-S", "--show-error", "-L", "--location", "-i", "--include",
           "-v", "--verbose", "-k", "--insecure", "--compressed", "-f", "--fail", "-#"}  # fmt: skip
IGNORED_WITH_VALUE = {
    "-o",
    "--output",
    "-m",
    "--max-time",
    "--connect-timeout",
    "-w",
    "--write-out",
}

# Short flags that take a value, which curl also accepts glued on: -XPOST, -H'Accept: x'.
SHORT_WITH_VALUE = {"-X", "-H", "-d", "-u", "-A", "-e", "-b", "-o", "-m", "-w"}


@dataclass
class ParsedCurl:
    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: str | None = None
    warnings: list[str] = field(default_factory=list)


def parse_curl(command: str) -> ParsedCurl:
    # Line continuations as copied from docs or DevTools: "\\\n" (bash) and "^\n" (cmd.exe).
    text = command.replace("\\\r\n", " ").replace("\\\n", " ").replace("^\n", " ").strip()
    try:
        args = shlex.split(text)
    except ValueError as exc:  # an unclosed quote
        raise ValidationFailedError(
            f"Couldn't parse the command: {exc}.", code="INVALID_CURL"
        ) from exc
    if not args or args[0] != "curl":
        raise ValidationFailedError("That doesn't start with `curl`.", code="INVALID_CURL")

    parsed = ParsedCurl()
    method: str | None = None
    data: list[str] = []
    args = args[1:]
    i = 0

    def value() -> str:
        nonlocal i
        i += 1
        if i >= len(args):
            raise ValidationFailedError(f"{args[i - 1]} needs a value.", code="INVALID_CURL")
        return args[i]

    while i < len(args):
        arg = args[i]
        # --flag=value is the same as --flag value
        if arg.startswith("--") and "=" in arg:
            flag, _, inline = arg.partition("=")
            args[i : i + 1] = [flag, inline]
            arg = flag
        # Short-flag shorthands: -XPOST is -X POST; -sSL is -s -S -L.
        elif len(arg) > 2 and arg[0] == "-" and arg[1] != "-":
            if arg[:2] in SHORT_WITH_VALUE:
                args[i : i + 1] = [arg[:2], arg[2:]]
            elif all(f"-{letter}" in IGNORED for letter in arg[1:]):
                args[i : i + 1] = [f"-{letter}" for letter in arg[1:]]
            arg = args[i]
        if arg in ("-X", "--request"):
            method = value().upper()
        elif arg in ("-H", "--header"):
            name, sep, header_value = value().partition(":")
            if not sep:
                parsed.warnings.append(f"Skipped a malformed header: {name!r}")
            else:
                parsed.headers[name.strip()] = header_value.strip()
        elif arg in DATA_FLAGS:
            data.append(value())
        elif arg == "--json":
            data.append(value())
            parsed.headers.setdefault("Content-Type", "application/json")
            parsed.headers.setdefault("Accept", "application/json")
        elif arg in ("-u", "--user"):
            token = base64.b64encode(value().encode()).decode()
            parsed.headers["Authorization"] = f"Basic {token}"
        elif arg in ("-A", "--user-agent"):
            parsed.headers["User-Agent"] = value()
        elif arg in ("-e", "--referer"):
            parsed.headers["Referer"] = value()
        elif arg in ("-b", "--cookie"):
            parsed.headers["Cookie"] = value()
        elif arg == "--url":
            parsed.url = value()
        elif arg in ("-I", "--head"):
            method = "HEAD"
        elif arg in IGNORED:
            pass
        elif arg in IGNORED_WITH_VALUE:
            value()
        elif arg.startswith("-"):
            parsed.warnings.append(f"Ignored an option DevFlow doesn't support: {arg}")
        elif not parsed.url:
            parsed.url = arg
        else:
            parsed.warnings.append(f"Ignored an extra argument: {arg}")
        i += 1

    if not parsed.url:
        raise ValidationFailedError("No URL found in the command.", code="INVALID_CURL")
    if data:
        # Several -d flags are joined with & — what curl itself sends.
        parsed.body = "&".join(data)
        if any(item.startswith("@") for item in data):
            parsed.warnings.append(
                "A -d @file reads a file on YOUR machine; paste its contents instead."
            )
        parsed.headers.setdefault("Content-Type", _guess_type(parsed.body))
    parsed.method = method or ("POST" if data else "GET")
    return parsed


def _guess_type(body: str) -> str:
    try:
        json.loads(body)
    except ValueError:
        return "application/x-www-form-urlencoded"  # curl's default for -d
    return "application/json"
