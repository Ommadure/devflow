# ADR 0008: Neon + an Oracle Always Free VM + Vercel

- **Status:** Accepted
- **Date:** 2026-09-26
- **Replaces:** the original "Supabase Postgres; API and worker on Render; Upstash Redis"

## Context
DevFlow must cost $0 to run, yet it needs things free platform tiers usually exclude: an
always-on background worker, a scheduler, Redis, and Postgres with pgvector.
ReviewPilot already runs on an Oracle Cloud Always Free VM (its ADR 0015).

## Decision
- **Frontend:** Vercel (static build) with a rewrite of `/api/*` to the API, so the
  browser stays same-origin.
- **API, worker, scheduler, Redis:** Docker Compose on the existing Oracle VM, next to
  ReviewPilot. One shared Caddy terminates TLS for both apps (only one process can bind
  ports 80/443).
- **Database:** Neon Postgres (free tier) with the `vector` extension. The API and worker
  use the pooled connection string; Alembic uses the direct one.
- **Local:** Docker Compose with the `pgvector/pgvector` image and Redis, on host ports
  5434 and 6380 so it can run beside ReviewPilot's stack.

## Consequences
- $0, with a real worker and scheduler instead of a sleeping free web service.
- The VM is a single point of failure shared by two apps, and memory is limited; the
  embedding model's footprint is planned for in Phase 7.
- Neon's free compute scales to zero, so the first query after idle is slower.
- Om operates the VM: OS updates, Docker, backups of anything not in Neon.

## Alternatives considered
- **Render + Upstash**: the free web service sleeps and background workers are paid.
- **Supabase Postgres**: also has pgvector, but its main draw was Auth, which ADR 0001
  replaces.
- **Postgres on the VM**: free, but then backups, upgrades and disk are Om's problem;
  Neon handles them.
