# ADR 0006: The API tester is proxied server-side, with SSRF protection

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
An HTTP client running in the browser can only call APIs that send permissive CORS
headers, so most real APIs fail with an opaque network error. Sending the request from the
server removes that limit — and turns the backend into something any user can point at
arbitrary URLs, the textbook setup for Server-Side Request Forgery.

## Decision
- `POST /api-tester/send` performs the request server-side.
- SSRF protection is mandatory and tested: `http`/`https` only; resolve DNS first and
  block private, loopback, link-local (including `169.254.169.254`), multicast, reserved
  and unspecified ranges for IPv4 and IPv6; connect to the **validated IP** while sending
  the original `Host`/SNI (defeats DNS rebinding); re-validate every redirect hop (max 3);
  15 s timeout; 2 MB response cap; hop-by-hop headers stripped.
- Rate-limited per user (30/min).

## Consequences
- The tester works with any public API.
- The VM's own services and the cloud metadata endpoint are unreachable through it.
- The code is security-critical; its tests are the specification.

## Alternatives considered
- **Browser-only fetch**: no SSRF risk, but CORS makes the feature mostly useless.
- **Block-list by hostname**: bypassed by DNS names that resolve to private IPs.
