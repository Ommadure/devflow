# ADR 0007: One repository, split by deployable

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
DevFlow has two languages (TypeScript, Python), two toolchains (npm, uv) and two deploy
targets (Vercel for the static frontend, a VM for the API, worker and scheduler). Changes
often touch both sides — a new endpoint and the page that uses it.

## Decision
- One repository with `frontend/` and `backend/` at the top, each self-contained (own
  lockfile, config, tests, CI job).
- Frontend types are generated from the backend's OpenAPI schema, so the contract is
  checked by the compiler.
- One PR per phase contains both halves of each feature.

## Consequences
- A feature and its UI land and are reviewed together; CI checks both.
- Vercel builds only `frontend/`; the backend image builds only `backend/`.

## Alternatives considered
- **Two repositories**: cleaner permissions, but every feature needs two coordinated PRs.
- **Monorepo tooling (Nx, Turborepo)**: built for many JavaScript packages; overkill for
  two apps in different languages.
