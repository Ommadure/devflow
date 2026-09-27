# DevFlow

A developer productivity dashboard — code snippets, markdown notes, a Pomodoro focus timer,
GitHub analytics and an HTTP API tester — with AI on top: hybrid semantic search, streaming
"explain this code", AI tag suggestions and "ask your notes" with citations.

**Stack:** React 19 + TypeScript + Redux Toolkit / RTK Query (Vite) · FastAPI + SQLAlchemy async · Postgres
+ pgvector · Redis · Taskiq · FastEmbed · Gemini.

> 🚧 **Being rebuilt from its specification, one phase at a time.** Phase 7 (search
> evaluation, hardening, deployment) is in review; the production deploy is next. See
> [the spec](docs/application-prompt.md) for the full design and
> [the ADRs](docs/adr/README.md) for why each choice was made.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold: spec, ADRs, empty backend and frontend, Docker Compose, CI | ✅ |
| 1 | Backend foundation and authentication | ✅ |
| 2 | Frontend shell and auth UI | ✅ |
| 3 | Snippets, notes, timer, dashboard | ✅ |
| 4 | Embeddings, Taskiq worker, hybrid search | ✅ |
| 5 | LLM features: explain, auto-tag, ask your notes | ✅ |
| 6 | API tester proxy, pomodoro stats, GitHub insights | ✅ |
| 7 | Search evaluation, hardening, deployment | 🟡 |

## Search quality

Measured on 60 realistic snippets and 30 queries, 16 of which describe the goal without
using the snippet's words ([evals/search](evals/search/README.md)):

| Mode | Recall@5 | MRR@10 | Recall@5, intent queries | p50 latency |
|---|---|---|---|---|
| keyword (Postgres full-text) | 0.33 | 0.33 | 0.00 | 10 ms |
| semantic (bge-small + pgvector) | 0.82 | 0.76 | 0.81 | 28 ms |
| **hybrid (RRF)** — the default | **0.85** | **0.79** | **0.81** | 32 ms |

The evaluation also set the semantic cut-off from data, and checking it at multi-user scale
found (and fixed) filtered HNSW scans silently dropping a user's own matches.

## Run it locally

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 22.12+.

```bash
cd backend && cp -n .env.example .env         # set JWT_SECRET and GEMINI_API_KEY (or LLM_PROVIDER=fake)
cd .. && docker compose up -d --build         # API :8000, worker, scheduler, Postgres :5434, Redis :6380
./backend/scripts/smoke_auth.sh               # register → refresh → change password → logout
cd frontend && npm install && npm run dev     # app on :5173 — create an account there
```

Prefer running the API outside Docker? `docker compose up -d postgres redis`, then
`cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --reload`.

API docs: http://localhost:8000/docs

**Try semantic search:** create an account in the app, then add a dozen demo snippets and
search for *"stop a function from firing too often"*:

```bash
docker compose exec api python scripts/seed_demo.py you@example.com
docker compose exec api python scripts/backfill_embeddings.py   # or let the worker do it
```

Changed an endpoint? `cd frontend && npm run gen:api` regenerates `openapi.json` and the
TypeScript types; CI fails if they're out of date.

## Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## Deployment

Frontend on Vercel (a `/api/v1` rewrite keeps the API same-origin, so the refresh cookie
is first-party); API, worker, scheduler and Redis on an Oracle Always Free A1 VM behind
Caddy; Postgres on Neon. Step by step: [docs/deploy.md](docs/deploy.md).
CI builds the production image on every change.

## Repository layout

```
backend/        FastAPI service, Taskiq worker and scheduler (one image)
frontend/       React app, deployed to Vercel (vercel.json: rewrite + CSP)
evals/search/   Search evaluation: dataset, runner, recorded results
deploy/oracle/  Production compose, Caddyfile, VM bootstrap and deploy scripts
docs/           Specification, deploy guide, architecture decision records
```
