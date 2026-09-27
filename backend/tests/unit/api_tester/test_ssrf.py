"""SSRF: every way the proxy could be pointed at our own network must be refused."""

import ipaddress

import pytest

from app.services.api_tester.ssrf import BlockedDestination, check_url, is_public

PUBLIC = "93.184.216.34"


def resolver(mapping: dict[str, list[str]]):  # type: ignore[no-untyped-def]
    async def resolve(host: str, port: int) -> list[str]:
        if host not in mapping:
            raise OSError("NXDOMAIN")
        return mapping[host]

    return resolve


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1", "127.8.9.10", "0.0.0.0",  # noqa: S104  loopback, unspecified
        "10.0.0.5", "172.16.0.1", "192.168.1.1",  # private
        "169.254.169.254",  # cloud metadata (AWS, GCP, Azure, Oracle)
        "100.64.0.1",  # carrier-grade NAT
        "224.0.0.1", "239.255.255.250",  # multicast: is_global says True!
        "255.255.255.255", "192.0.2.1", "198.18.0.1",  # broadcast, documentation, benchmarking
        # IPv6 loopback, unspecified, link-local, ULA (AWS's IPv6 metadata), multicast
        "::1", "::", "fe80::1", "fd00:ec2::254", "ff02::1",
        "::ffff:127.0.0.1", "::ffff:169.254.169.254",  # IPv4-mapped
        # NAT64 wrapping 10.0.0.1 and 127.0.0.1: is_global says True!
        "64:ff9b::a00:1", "64:ff9b::7f00:1",
        "2002:7f00:1::",  # 6to4 wrapping 127.0.0.1
    ],
)  # fmt: skip
def test_private_and_special_addresses_are_not_public(address: str) -> None:
    assert not is_public(ipaddress.ip_address(address))


@pytest.mark.parametrize("address", [PUBLIC, "8.8.8.8", "2606:4700:4700::1111", "64:ff9b::808:808"])
def test_ordinary_internet_addresses_are_public(address: str) -> None:
    assert is_public(ipaddress.ip_address(address))


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/api/v1/me",
        "http://169.254.169.254/latest/meta-data/iam/",
        "http://[::1]:6379/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0:8000/",
    ],
)
async def test_internal_urls_are_refused(url: str) -> None:
    with pytest.raises(BlockedDestination) as caught:
        await check_url(url, resolver({"localhost": ["127.0.0.1", "::1"]}))
    assert caught.value.code == "BLOCKED_DESTINATION"


async def test_a_public_name_that_resolves_to_a_private_address_is_refused() -> None:
    """The DNS trick: the hostname looks harmless, the address isn't."""
    with pytest.raises(BlockedDestination):
        await check_url(
            "https://totally-legit.example/", resolver({"totally-legit.example": ["10.1.2.3"]})
        )


async def test_any_private_address_among_several_is_enough_to_refuse() -> None:
    with pytest.raises(BlockedDestination):
        await check_url(
            "https://mixed.example/", resolver({"mixed.example": [PUBLIC, "127.0.0.1"]})
        )


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("file:///etc/passwd", "INVALID_URL"),
        ("gopher://example.com/", "INVALID_URL"),
        ("ftp://example.com/", "INVALID_URL"),
        ("http:///no-host", "INVALID_URL"),
        ("https://user:secret@example.com/", "INVALID_URL"),
        ("http://example.com:99999/", "INVALID_URL"),
        ("https://does-not-exist.example/", "DNS_FAILED"),
    ],
)
async def test_bad_urls_are_refused_with_a_reason(url: str, code: str) -> None:
    with pytest.raises(BlockedDestination) as caught:
        await check_url(url, resolver({"example.com": [PUBLIC]}))
    assert caught.value.code == code


async def test_a_public_url_is_pinned_to_the_address_that_was_checked() -> None:
    target = await check_url(
        "https://api.example.com:8443/v1?x=1", resolver({"api.example.com": [PUBLIC]})
    )
    assert (target.host, target.port, target.address) == ("api.example.com", 8443, PUBLIC)
