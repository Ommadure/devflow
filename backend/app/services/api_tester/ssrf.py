"""SSRF protection for the API tester proxy (ADR 0006, spec §11.6).

The proxy fetches URLs a user typed, from inside our network. Without these checks a user
could make the server call its own neighbours: the cloud metadata service at
169.254.169.254 (which can hand out credentials), Redis on the internal network, the API
itself on 127.0.0.1. So every destination is checked by the ADDRESS it resolves to — a
hostname check alone is bypassed by any public name that resolves to a private address.

Two lessons baked in (both have tests):
- `ipaddress.is_global` is not enough: multicast (224.0.0.1) and NAT64 (64:ff9b::/96,
  which can wrap 10.0.0.1) both report is_global=True.
- IPv6 can embed IPv4 (::ffff:a.b.c.d, 64:ff9b::a.b.c.d, 2002:aabb:ccdd::) — unwrap and
  check the IPv4 inside too.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

from app.core.errors import ValidationFailedError

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str, int], Awaitable[list[str]]]

NAT64 = ipaddress.ip_network("64:ff9b::/96")
SIX_TO_FOUR = ipaddress.ip_network("2002::/16")


class BlockedDestination(ValidationFailedError):
    default_code = "BLOCKED_DESTINATION"


@dataclass(frozen=True)
class Target:
    url: SplitResult
    host: str  # as the user wrote it: sent as Host and as the TLS server name
    port: int
    address: str  # the checked IP we actually connect to


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip in SIX_TO_FOUR:
        return ip.sixtofour
    return None


def is_public(ip: IPAddress) -> bool:
    """True only for ordinary internet addresses: global unicast, nothing wrapped inside."""
    if not ip.is_global or ip.is_multicast:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        inner = _embedded_ipv4(ip)
        if inner is not None and not is_public(inner):
            return False
    return True


async def system_resolver(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
    )
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


async def check_url(url: str, resolve: Resolver = system_resolver) -> Target:
    """Validate a URL and pin it to one checked address. Called for EVERY redirect hop."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        raise BlockedDestination("That URL can't be parsed.", code="INVALID_URL") from exc
    if parts.scheme not in ("http", "https"):
        raise BlockedDestination("Only http:// and https:// URLs are allowed.", code="INVALID_URL")
    if not parts.hostname:
        raise BlockedDestination("The URL needs a host name.", code="INVALID_URL")
    if parts.username or parts.password:
        # user:pass@host hides a credential in the URL (and in logs); use an
        # Authorization header instead (Import cURL converts -u for you).
        raise BlockedDestination(
            "Put credentials in an Authorization header, not in the URL.", code="INVALID_URL"
        )

    host = parts.hostname
    try:
        literal: IPAddress | None = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = [str(literal)]
    else:
        try:
            addresses = await resolve(host, port)
        except (OSError, UnicodeError) as exc:
            raise BlockedDestination(f"Couldn't resolve {host}.", code="DNS_FAILED") from exc
    if not addresses:
        raise BlockedDestination(f"Couldn't resolve {host}.", code="DNS_FAILED")

    # Every address must be public: a name resolving to [public, private] could otherwise
    # be connected to the private one.
    for address in addresses:
        if not is_public(ipaddress.ip_address(address)):
            raise BlockedDestination(
                "That address is on a private or reserved network, which the tester can't reach.",
                details={"host": host},
            )
    # Connect to the address we checked — not to whatever a second DNS lookup returns. A
    # DNS-rebinding attacker answers "public" to the check and "127.0.0.1" to the connect.
    return Target(url=parts, host=host, port=port, address=addresses[0])
