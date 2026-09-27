"""Send the user's request from the server, safely (ADR 0006, spec §11.6).

- Destination checked by resolved address (ssrf.py), and connected to by that address,
  with the original host kept for the Host header and TLS (SNI + certificate check).
- Redirects followed by hand, at most 3, each hop checked again: a public URL may redirect
  to http://169.254.169.254/.
- 15 s for the whole exchange; the response is read up to 2 MB, then cut and flagged.
- Hop-by-hop headers are dropped in both directions; environment proxies are ignored.
"""

import asyncio
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal
from urllib.parse import urljoin

import httpx

from app.core.errors import UpstreamError, ValidationFailedError
from app.services.api_tester.ssrf import Resolver, Target, check_url, system_resolver

Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

TIMEOUT_SECONDS = 15.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
# RFC 9110 §7.6.1: these describe one connection, not the message; never forwarded.
HOP_BY_HOP = frozenset(
    {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer",
     "transfer-encoding", "upgrade", "proxy-connection"}
)  # fmt: skip
# Set by us from the checked target; a user-supplied value could smuggle a different host.
OURS = frozenset({"host", "content-length"})


@lru_cache
def proxy_http_client() -> httpx.AsyncClient:
    """Separate from every other client: never follows redirects on its own (each hop must
    be checked), and ignores HTTP_PROXY/HTTPS_PROXY from the environment (trust_env=False)
    so a stray proxy variable can't route user requests somewhere unexpected."""
    return httpx.AsyncClient(
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(TIMEOUT_SECONDS),
        limits=httpx.Limits(max_connections=20),
    )


@dataclass
class ProxyResult:
    status: int
    status_text: str
    headers: list[tuple[str, str]]
    body: str
    body_truncated: bool
    elapsed_ms: int
    size_bytes: int
    final_url: str
    redirects: list[str] = field(default_factory=list)


def _request(
    method: str, target: Target, headers: dict[str, str], body: bytes | None
) -> httpx.Request:
    netloc = f"[{target.address}]" if ":" in target.address else target.address
    if target.url.port:
        netloc += f":{target.url.port}"
    url = target.url._replace(netloc=netloc).geturl()
    host_header = target.host if not target.url.port else f"{target.host}:{target.url.port}"
    clean = {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP | OURS}
    return httpx.Request(
        method,
        url,
        headers={**clean, "Host": host_header},
        content=body,
        # TLS to the IP, but the certificate is verified for the name the user asked for.
        extensions={"sni_hostname": target.host},
    )


async def send(
    client: httpx.AsyncClient,
    method: Method,
    url: str,
    headers: dict[str, str],
    body: str | None,
    *,
    resolve: Resolver = system_resolver,
) -> ProxyResult:
    started = time.monotonic()
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            return await _exchange(client, method, url, headers, body, resolve, started)
    except TimeoutError as exc:
        raise UpstreamError(
            f"No complete response within {TIMEOUT_SECONDS:.0f} seconds.", code="PROXY_TIMEOUT"
        ) from exc
    except httpx.HTTPError as exc:
        raise UpstreamError(
            f"Couldn't reach the server: {type(exc).__name__}.", code="PROXY_UNREACHABLE"
        ) from exc


async def _exchange(
    client: httpx.AsyncClient,
    method: Method,
    url: str,
    headers: dict[str, str],
    body: str | None,
    resolve: Resolver,
    started: float,
) -> ProxyResult:
    payload = body.encode() if body else None
    current, redirects = url, list[str]()
    while True:
        target = await check_url(current, resolve)
        response = await client.send(_request(method, target, headers, payload), stream=True)
        try:
            location = response.headers.get("location")
            if response.is_redirect and location:
                if len(redirects) >= MAX_REDIRECTS:
                    raise ValidationFailedError(
                        f"More than {MAX_REDIRECTS} redirects.", code="TOO_MANY_REDIRECTS"
                    )
                redirects.append(current)
                current = urljoin(current, location)
                # 303 always, and 301/302 after a POST, become a GET without a body
                # (what browsers do); 307/308 keep the method and body.
                if response.status_code == 303 or (
                    response.status_code in (301, 302) and method == "POST"
                ):
                    method, payload = "GET", None
                continue
            content, truncated, size = await _read_capped(response)
        finally:
            await response.aclose()
        return ProxyResult(
            status=response.status_code,
            status_text=response.reason_phrase,
            headers=[
                (k, v) for k, v in response.headers.multi_items() if k.lower() not in HOP_BY_HOP
            ],
            body=content.decode(response.encoding or "utf-8", errors="replace"),
            body_truncated=truncated,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            size_bytes=size,
            final_url=current,
            redirects=redirects,
        )


async def _read_capped(response: httpx.Response) -> tuple[bytes, bool, int]:
    """Read at most MAX_RESPONSE_BYTES of the DECODED body: a 5 GB download must not fill the
    server's memory, and neither may a few KB of gzip that inflate to gigabytes (a zip
    bomb) — aiter_bytes() decompresses as it goes, so the cap stops that early too."""
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        chunks.append(chunk)
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            return b"".join(chunks)[:MAX_RESPONSE_BYTES], True, size
    return b"".join(chunks), False, size
