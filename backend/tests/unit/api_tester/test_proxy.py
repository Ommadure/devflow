"""The proxy's behaviour against fake servers (respx): pinning, redirects, limits."""

import gzip
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from app.core.errors import UpstreamError, ValidationFailedError
from app.services.api_tester import proxy
from app.services.api_tester.ssrf import BlockedDestination

PUBLIC, OTHER = "93.184.216.34", "93.184.216.35"


async def resolve(host: str, port: int) -> list[str]:
    return {"api.example.com": [PUBLIC], "cdn.example.com": [OTHER], "evil.example": ["10.0.0.1"]}[
        host
    ]


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(trust_env=False) as c:
        yield c


async def send(
    client: httpx.AsyncClient,
    url: str,
    *,
    method: proxy.Method = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
) -> proxy.ProxyResult:
    return await proxy.send(client, method, url, headers or {}, body, resolve=resolve)


@respx.mock
async def test_connects_to_the_checked_ip_but_keeps_the_host_for_http_and_tls(
    client: httpx.AsyncClient,
) -> None:
    route = respx.get(f"https://{PUBLIC}/users?page=2").respond(
        json={"ok": True}, headers={"X-Id": "7"}
    )
    result = await send(
        client, "https://api.example.com/users?page=2", headers={"Accept": "application/json"}
    )

    request = route.calls.last.request
    assert request.headers["host"] == "api.example.com"
    assert (
        request.extensions["sni_hostname"] == "api.example.com"
    )  # certificate checked for the name
    assert (result.status, result.status_text, result.body) == (200, "OK", '{"ok":true}')
    assert ("x-id", "7") in result.headers


@respx.mock
async def test_the_user_cannot_override_host_or_send_hop_by_hop_headers(
    client: httpx.AsyncClient,
) -> None:
    route = respx.post(f"https://{PUBLIC}/").respond(204)
    smuggled = {
        "Host": "internal.local",
        "Connection": "keep-alive, X-Secret",
        "Content-Length": "999",
    }
    await send(client, "https://api.example.com/", method="POST", body="{}", headers=smuggled)
    request = route.calls.last.request
    assert request.headers["host"] == "api.example.com"
    assert request.headers.get("connection") != "keep-alive, X-Secret"
    assert request.headers["content-length"] == "2"


@respx.mock
async def test_redirects_are_followed_and_each_hop_is_checked(client: httpx.AsyncClient) -> None:
    respx.get(f"https://{PUBLIC}/old").respond(
        301, headers={"Location": "https://cdn.example.com/new"}
    )
    respx.get(f"https://{OTHER}/new").respond(200, text="moved")
    result = await send(client, "https://api.example.com/old")
    assert (result.body, result.final_url) == ("moved", "https://cdn.example.com/new")
    assert result.redirects == ["https://api.example.com/old"]


@respx.mock
async def test_a_redirect_into_the_private_network_is_refused(client: httpx.AsyncClient) -> None:
    """The classic bypass: a public URL that redirects to the metadata service."""
    respx.get(f"https://{PUBLIC}/go").respond(
        302, headers={"Location": "http://169.254.169.254/latest/meta-data/"}
    )
    with pytest.raises(BlockedDestination):
        await send(client, "https://api.example.com/go")


@respx.mock
async def test_a_redirect_to_a_name_resolving_privately_is_refused(
    client: httpx.AsyncClient,
) -> None:
    respx.get(f"https://{PUBLIC}/go").respond(307, headers={"Location": "https://evil.example/"})
    with pytest.raises(BlockedDestination):
        await send(client, "https://api.example.com/go")


@respx.mock
async def test_redirect_loops_stop_after_three(client: httpx.AsyncClient) -> None:
    respx.get(f"https://{PUBLIC}/loop").respond(302, headers={"Location": "/loop"})
    with pytest.raises(ValidationFailedError) as caught:
        await send(client, "https://api.example.com/loop")
    assert caught.value.code == "TOO_MANY_REDIRECTS"


@respx.mock
async def test_see_other_turns_a_post_into_a_get(client: httpx.AsyncClient) -> None:
    respx.post(f"https://{PUBLIC}/form").respond(303, headers={"Location": "/done"})
    done = respx.get(f"https://{PUBLIC}/done").respond(200, text="ok")
    await send(client, "https://api.example.com/form", method="POST", body="a=1")
    assert done.calls.last.request.content == b""


@respx.mock
async def test_large_bodies_are_cut_at_2_mb_and_flagged(client: httpx.AsyncClient) -> None:
    respx.get(f"https://{PUBLIC}/big").respond(
        200, content=b"x" * (proxy.MAX_RESPONSE_BYTES + 5000)
    )
    result = await send(client, "https://api.example.com/big")
    assert result.body_truncated
    assert len(result.body) == proxy.MAX_RESPONSE_BYTES


@respx.mock
async def test_a_gzip_bomb_is_capped_after_decompression(client: httpx.AsyncClient) -> None:
    bomb = gzip.compress(b"0" * (10 * 1024 * 1024))  # ~10 KB on the wire, 10 MB inflated
    respx.get(f"https://{PUBLIC}/bomb").respond(
        200, content=bomb, headers={"Content-Encoding": "gzip"}
    )
    result = await send(client, "https://api.example.com/bomb")
    assert result.body_truncated and len(result.body) == proxy.MAX_RESPONSE_BYTES


@respx.mock
async def test_unreachable_and_slow_servers_are_clean_errors(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(f"https://{PUBLIC}/down").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(UpstreamError) as caught:
        await send(client, "https://api.example.com/down")
    assert caught.value.code == "PROXY_UNREACHABLE"

    monkeypatch.setattr(proxy, "TIMEOUT_SECONDS", 0.05)
    respx.get(f"https://{PUBLIC}/slow").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(UpstreamError):
        await send(client, "https://api.example.com/slow")
