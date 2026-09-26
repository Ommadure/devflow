# DevFlow

A developer productivity dashboard — code snippets, markdown notes, a Pomodoro focus timer,
GitHub analytics and an HTTP API tester — with AI on top: hybrid semantic search, streaming
"explain this code", AI tag suggestions and "ask your notes" with citations.

**Stack:** React + TypeScript + Redux Toolkit (Vite) · FastAPI + SQLAlchemy async · Postgres
+ pgvector · Redis · Taskiq · FastEmbed · Gemini.

> 🚧 **Being rebuilt from its specification, one phase at a time.** Phase 0 (scaffold) is in
> progress. See [the spec](docs/application-prompt.md) for the full design and
> [the ADRs](docs/adr/README.md) for why each choice was made.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold: spec, ADRs, empty backend and frontend, Docker Compose, CI | 🟡 |
| 1 | Backend foundation and authentication | ⏳ |
| 2 | Frontend shell and auth UI | ⏳ |
| 3 | Snippets, notes, timer, dashboard | ⏳ |
| 4 | Embeddings, Taskiq worker, hybrid search | ⏳ |
| 5 | LLM features: explain, auto-tag, ask your notes | ⏳ |
| 6 | API tester proxy, pomodoro stats, GitHub insights | ⏳ |
| 7 | Search evaluation, hardening, deployment | ⏳ |

## Run it locally

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 22.12+.

```bash
docker compose up -d                          # Postgres + pgvector on :5434, Redis on :6380
cd backend && uv sync && uv run uvicorn app.main:app --reload   # API on :8000
cd frontend && npm install && npm run dev     # app on :5173
```

## Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## Repository layout

```
backend/    FastAPI service (and, from Phase 4, the Taskiq worker and scheduler)
frontend/   React app, deployed to Vercel
docs/       Specification and architecture decision records
```
