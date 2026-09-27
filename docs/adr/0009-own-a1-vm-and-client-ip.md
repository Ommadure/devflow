# ADR 0009: DevFlow gets its own A1 VM; the API trusts the forwarded client IP

- **Status:** Accepted
- **Date:** 2026-09-27
- **Supersedes:** the "next to ReviewPilot, one shared Caddy" part of ADR 0008

## Context
ADR 0008 planned to run DevFlow on ReviewPilot's Oracle VM. Measured on 2026-09-27, that
VM is the fallback shape, an E2.1.Micro: 1 GB of RAM with ~280 MB free and 411 MB
already in swap. DevFlow's production stack, measured in a local rehearsal of
`deploy/oracle/compose.yaml`, needs ~735 MB (API 307 MB and worker 323 MB with the
embedding model loaded, scheduler 79 MB, Redis 10 MB, Caddy 16 MB).

In production the browser calls `/api/v1/*` on the Vercel domain and Vercel proxies it to
the VM, so the peer the API sees is a Vercel edge server, not the user.

## Decision
- **An Oracle A1 Flex (ARM) VM for DevFlow alone** (Always Free: up to 4 OCPU / 24 GB of
  A1 in total). Its own Caddy, its own DuckDNS name, its own compose project. The image is
  built on the VM, so natively for aarch64 (every dependency ships ARM wheels).
- **Redis runs on the VM** (append-only, `noeviction`), not a hosted free tier: the
  Taskiq stream needs a Redis that doesn't expire or cap commands.
- **Client IP:** Caddy trusts `X-Forwarded-For` from any peer and uvicorn takes the
  leftmost address, which Vercel sets to the real user. Per-IP rate limits (login,
  register) then apply per user, as intended.

## Consequences
- ReviewPilot is untouched; the two apps fail, deploy and scale independently.
- A1 capacity in Singapore is often "out of host capacity"; creating the VM can take
  retries (docs/deploy.md).
- **The client IP can be faked by anyone who calls the VM directly** (skipping Vercel),
  so per-IP limits are a speed bump, not a wall. What doesn't depend on it: the per-email
  login limit, argon2's cost per guess, and every per-user limit and quota. Accepted for a
  portfolio app; the fix, if ever needed, is to let only Vercel reach the API (a secret
  header added at the edge, or Cloudflare in front with authenticated origin pulls).

## Alternatives considered
- **Share ReviewPilot's 1 GB VM:** both apps would live in swap; search latency and
  ReviewPilot's reviews would suffer.
- **A second free E2.1.Micro:** fits only with heavy trimming (one model copy, swap) and
  no headroom.
- **Caddy's default (don't trust forwarded headers):** unforgeable, but every user shares
  a few Vercel edge IPs, so one noisy client could lock everyone out of signing in.
