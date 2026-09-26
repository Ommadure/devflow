# Working on DevFlow

Read [docs/application-prompt.md](docs/application-prompt.md) first — it is the full
specification — and [docs/adr/](docs/adr/README.md) for the reasoning behind it.

## Rules that are easy to miss

- **Phases are gated.** One phase per branch and PR; never start the next phase until Om
  confirms the current one. Each phase ends with verify commands, the key concepts, and
  three interview questions with model answers.
- **Backend layering:** routes → services → repositories. Every repository method takes
  `user_id` and filters by it; another user's row is a 404.
- **Frontend:** `@/` imports; pages compose, features decide; every backend call is an RTK
  Query endpoint in `features/<name>/api/`.
- **Tests ship with the feature** and never call a paid or external API.
- **Every new dependency needs a one-line reason.** Show migration SQL before applying it.
- **No secrets in git or in `VITE_` variables.**

## Commands

```bash
docker compose up -d
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

Local ports: Postgres 5434, Redis 6380, API 8000, frontend 5173.
