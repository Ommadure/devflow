# DevFlow — Application Prompt

A complete description of DevFlow, frontend and backend, for anyone — human or AI agent —
who needs to understand, extend, or build it. Paste this whole file as the opening
context of a working session.

> **History.** DevFlow began as a React + Supabase app that was being migrated behind a
> FastAPI backend. That code was deleted on 2026-09-26 and the project is being **rebuilt
> from this specification, API-first**: the frontend talks only to the FastAPI backend
> from day one, the backend owns authentication, and data lives in Neon Postgres. The
> [ADRs](adr/README.md) record why each of these choices was made. If this file and the
> code disagree, the code wins — and this file should be fixed.

**Phase markers:** each feature is tagged with the phase that builds it — **P0** … **P7**
(Section 15). The status table in Section 3 says which phases are done.

---

## 1. Your role

You are a senior full-stack engineer working with **Om**, a frontend developer moving into
Python/AI full-stack roles. DevFlow is a resume project: Om must be able to explain and
defend every decision in an interview. That shapes how you work:

1. **Work in phases** (Section 15). Never start the next phase until Om confirms the
   current one is done. One phase = one branch = one pull request.
2. **End every phase with:** files changed, exact commands to verify locally, the key
   concepts explained simply, and three interview questions with strong model answers.
3. **The app must work after every phase.** Each phase ships a vertical slice — backend,
   frontend and tests together.
4. **Check the code before asking; ask before assuming.** Do not invent tables, columns,
   APIs, or library behaviour. If unsure how a library or external API behaves, say so and
   check the official docs.
5. **Tests are part of the work,** not a follow-up.
6. **No secrets in code or git.** Everything comes from environment variables.
7. **Prefer boring, explainable solutions.** Every new dependency needs a reason Om can
   repeat.

---

## 2. What DevFlow is

A developer productivity dashboard. One signed-in user keeps their own:

| Module | What it does | Route | Phase |
|---|---|---|---|
| **Dashboard** | Tiles linking to each tool, with counts of snippets, notes and focus sessions | `/` | P3 |
| **Snippet Manager** | Save, edit, delete, copy, search and tag-filter code snippets | `/snippets` | P3 |
| **Markdown Notes** | Notes with a live preview and debounced auto-save | `/notes` | P3 |
| **Focus Timer** | A 25-minute focus / 5-minute break Pomodoro timer that records completed sessions | `/timer` | P3 |
| **GitHub Analytics** | Look up any public GitHub user: profile and six most recent repositories | `/github` | P6 |
| **HTTP API Tester** | Compose and send an HTTP request, inspect status, timing, headers and body | `/api` | P6 |
| **Settings** | Account email, password change, and an API connection check | `/settings` | P2 |

On top of those, AI features: hybrid semantic search over snippets (P4), streaming
"explain this code", AI tag suggestions and "ask your notes" with citations (P5), a
server-side API tester with SSRF protection, Pomodoro statistics and weekly GitHub
insights (P6).

---

## 3. Current status

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold: repo, spec, ADRs, empty backend and frontend, Docker Compose, CI | 🟡 in progress |
| 1 | Backend foundation and authentication | ⏳ |
| 2 | Frontend shell and auth UI | ⏳ |
| 3 | Snippets, notes, timer, dashboard | ⏳ |
| 4 | pgvector, embeddings, Taskiq worker, hybrid search | ⏳ |
| 5 | LLM features: explain, auto-tag, ask your notes; quotas and rate limits | ⏳ |
| 6 | API tester proxy, pomodoro stats, GitHub overview and insights | ⏳ |
| 7 | Search evaluation, hardening, production deployment | ⏳ |

---

## 4. Architecture

```
┌──────────────── Vercel ────────────────┐        ┌──────────── Oracle Cloud VM ─────────────┐
│ React + TS + RTK Query (static build)  │        │  Caddy (TLS, shared with ReviewPilot)     │
│                                        │ /api/* │    │                                      │
│ Browser calls same-origin /api/* ──────┼───────►│  FastAPI (api)                            │
│ ◄──────────── JSON / SSE ──────────────┼────────│   issues + verifies JWTs · scopes every   │
└────────────────────────────────────────┘rewrite │   query by user_id · rate limits          │
                                                  │    │ enqueue             │ LLM / GitHub   │
                                                  │  ┌─▼─────┐               ▼                │
                                                  │  │ Redis │         external APIs          │
                                                  │  └─┬─────┘                                │
                                                  │  ┌─▼──────────────────┐ ┌───────────────┐ │
                                                  │  │ Taskiq worker      │ │ Taskiq        │ │
                                                  │  │ embeddings·insights│ │ scheduler     │ │
                                                  │  └────────────────────┘ └───────────────┘ │
                                                  └───────────────┬───────────────────────────┘
                                                                  │ SQLAlchemy + asyncpg (TLS)
                                                        ┌─────────▼──────────┐
                                                        │ Neon Postgres       │
                                                        │ + pgvector          │
                                                        └────────────────────┘
```

The browser only ever talks to its own origin. Vite's dev proxy (locally) and a Vercel
rewrite (in production) forward `/api/*` to FastAPI, so the refresh-token cookie is
first-party and no CORS preflight is needed.

### Decisions that shape everything ([adr/](adr/README.md))

| # | Decision | The one-line reason |
|---|---|---|
| 0001 | The API owns auth: email + password, short-lived access JWT, rotating refresh cookie | Om can explain every link of the auth chain; no third-party auth to depend on |
| 0002 | Every query is scoped by `user_id` in the repository layer; another user's row is a 404 | With no RLS, the API is the only access control — so it is enforced in one layer and tested |
| 0003 | Taskiq for background jobs | Async-native like the rest of the backend and actively maintained (ARQ is maintenance-only) |
| 0004 | FastEmbed `bge-small-en-v1.5` locally | Free, 384 dims, ONNX so no PyTorch in the image |
| 0005 | Reciprocal Rank Fusion for hybrid search | Keyword and vector scores live on different scales; ranks don't |
| 0006 | API tester proxied server-side | Removes browser CORS limits — and makes SSRF protection mandatory |
| 0007 | Monorepo split by deployable | Two languages, two toolchains, two deploy targets |
| 0008 | Neon Postgres + an Oracle Always Free VM + Vercel | $0 hosting that still runs a real worker and scheduler |

---

## 5. Tech stack

### Frontend

| Concern | Choice | Phase |
|---|---|---|
| Build | Vite 8 | P0 |
| UI | React 18 + TypeScript 6 | P0 |
| Styling | Tailwind CSS 4 (`@tailwindcss/vite`) + `@tailwindcss/typography` | P0 / P3 |
| Routing | React Router 7, every route lazy-loaded | P2 |
| Client + server state | Redux Toolkit; RTK Query for every backend call | P2 |
| Markdown | `react-markdown` + `remark-gfm` (raw HTML is escaped by default, so no DOMPurify) | P3 |
| Motion / icons / dates | motion · lucide-react · date-fns | P2 |
| Tests | Vitest + Testing Library + jsdom | P0 |
| API types | `openapi-typescript` generated from the FastAPI schema | P2 |

### Backend

| Concern | Choice | Phase |
|---|---|---|
| Language / packaging | Python 3.12, `uv` with a lockfile | P0 |
| Framework | FastAPI | P0 |
| Settings / validation | Pydantic v2, `pydantic-settings` | P1 |
| Database | SQLAlchemy 2.0 async + `asyncpg`, Alembic | P1 |
| Passwords | `argon2-cffi` (argon2id) | P1 |
| Tokens | PyJWT (HS256 access tokens) | P1 |
| Cache / queue / limits | Redis | P1 |
| Logging / errors | structlog (JSON in production) · Sentry when `SENTRY_DSN` is set | P1 |
| Quality | Ruff (lint + format), mypy `--strict` | P0 |
| Tests | pytest, pytest-asyncio, httpx `AsyncClient`, respx | P0 |
| Background jobs | Taskiq + `taskiq-redis` (worker and scheduler) | P4 |
| Vectors / embeddings | pgvector, FastEmbed | P4 |
| LLM | provider interface; Gemini default; OpenAI-compatible swappable; fake for tests | P5 |

### Infrastructure

| Concern | Choice | Phase |
|---|---|---|
| Local stack | Docker Compose: pgvector Postgres (host port **5434**), Redis (host port **6380**) | P0 |
| CI | GitHub Actions: backend + frontend jobs | P0 |
| Frontend hosting | Vercel, Root Directory = `frontend`, `/api/*` rewritten to the VM | P7 |
| API + worker + scheduler | Docker Compose on an Oracle Always Free VM behind Caddy | P7 |
| Database | Neon Postgres with the `vector` extension | P7 |

---

## 6. Repository structure

```
devflow/
├── frontend/                 React app — Vercel deploys this folder
│   ├── src/
│   │   ├── main.tsx          Entry
│   │   ├── app/              App shell, providers, route table, Redux store
│   │   ├── pages/            One component per route; composition only
│   │   ├── features/<name>/  api/ (RTK Query endpoints) · store/ (slice) · hooks/ · lib/ · types.ts · index.ts
│   │   ├── components/       ui/ (Modal, ConfirmDialog, loaders, ApiConnectionCard) · layout/ (AppLayout)
│   │   ├── lib/              api/ (base query, errors, SSE, generated schema) · utils/cn.ts
│   │   ├── hooks/ styles/ types/ test/
│   ├── vite.config.ts  vercel.json  package.json
├── backend/                  FastAPI service, Taskiq worker and scheduler (one image)
│   ├── app/
│   │   ├── main.py           App factory: middleware, routers, handlers, lifespan
│   │   ├── core/             config · security · errors · logging · middleware · redis · rate_limit
│   │   ├── db/               async engine, per-request session, declarative Base
│   │   ├── api/v1/routes/    one module per resource
│   │   ├── schemas/          Pydantic request/response models
│   │   ├── models/           SQLAlchemy models
│   │   ├── repositories/     data access, always scoped by user_id
│   │   ├── services/         business logic; services/ai/ for LLM, embeddings, redaction, usage
│   │   ├── workers/          Taskiq broker, tasks, schedules
│   ├── alembic/versions/
│   ├── tests/unit/ tests/integration/
│   ├── Dockerfile  pyproject.toml  uv.lock  .env.example
├── evals/search/             Search evaluation (P7)
├── deploy/oracle/            Production compose + Caddy config (P7)
├── docs/                     This file, ADRs
├── docker-compose.yml
├── .github/workflows/ci.yml
└── AGENTS.md  README.md
```

### Rules

**Frontend**

- Imports use the `@/` alias, never `../../`.
- **Pages compose; features decide.** Pages render and dispatch. Logic and data access
  belong to a feature.
- **Every backend call is an RTK Query endpoint in `features/<name>/api/`**, injected into
  the one `baseApi`. Nothing calls `fetch` directly except `lib/api/` (base query, SSE).
- Cross-feature imports go through the barrel (`@/features/notes`), not deep paths.
- A page's file name matches its component: `SnippetsPage.tsx` exports `SnippetsPage`.

**Backend — layering**

`routes → services → repositories → database`

- Routes contain no SQL and no business logic.
- Repositories contain no business logic. **Every method takes `user_id` and filters by
  it.** No method may read or write another user's row.
- Services never import FastAPI objects.
- Another user's resource returns **404**, not 403 — a 403 confirms the row exists.

---

## 7. Frontend

### 7.1 Boot sequence (P2)

1. `main.tsx` renders `<AppProviders>` (Redux store) around `<App>`.
2. `App` runs a **silent refresh** once: `POST /api/v1/auth/refresh`. The browser sends
   the HttpOnly refresh cookie automatically; a success returns an access token and the
   user, which go into the `auth` slice.
3. While that request is in flight, a full-page spinner shows.
4. **No session** (401) → only `AuthPage` renders. No route is mounted.
   **Signed in** → `AppLayout` wraps `AppRoutes`.

The access token lives **only in Redux memory** — never `localStorage` — so an XSS bug
cannot read a long-lived credential. A page reload loses it; the silent refresh gets a new
one.

### 7.2 Routing (P2)

Defined in `app/routes.tsx`, every page `React.lazy`-loaded so each is its own chunk.
Unknown paths redirect to `/`.

### 7.3 Layout (P2)

`AppLayout`: a fixed sidebar on desktop, a slide-in drawer with an overlay on mobile, a
"skip to main content" link, `aria-current` on the active link, the signed-in email and a
Sign Out button. Navigation items: Dashboard, GitHub Analytics, Snippets, Notes, Timer,
API Tester, Settings.

### 7.4 State

| Slice | State | Phase |
|---|---|---|
| `auth` | `{ user, accessToken, status: 'checking' \| 'authenticated' \| 'anonymous' }` | P2 |
| `notes` | `{ activeNoteId }` — UI state only | P3 |
| `timer` | `{ mode, remainingSeconds, running }` — the countdown itself runs in the browser | P3 |
| `api` | RTK Query cache for every server collection (snippets, notes, sessions, …) | P2+ |

Server data is **never** copied into a hand-written slice. RTK Query owns it: cache tags
(`Me`, `Snippet`, `Note`, `PomodoroSession`, `Dashboard`, …) drive refetching after
mutations, and every mutation surfaces its error to the user.

### 7.5 Backend client (P2)

In `lib/api/`:

- `createApi` with one base query, `reducerPath: 'api'`, and endpoints injected by each
  feature.
- Base URL is the same-origin path `/api/v1`. `fetch` sends same-origin cookies by
  default, and the refresh cookie's `Path=/api/v1/auth` keeps it off every other request.
- The base query reads the access token from Redux **per request** and sets
  `Authorization: Bearer <access_token>`.
- **On 401:** call `/auth/refresh` once and retry. If the refresh fails, clear the session.
  Concurrent 401s share **one** refresh promise so they cannot race — and because refresh
  tokens rotate, a second parallel refresh would present an already-used token and revoke
  the whole session.
- `toApiError()` maps every failure — backend error bodies, dropped connections
  (`FETCH_ERROR` → `NETWORK_ERROR`), a proxy's HTML page — to a typed `ApiError`
  `{ status, code, message, details, requestId }`.
- On 429: a toast with the retry time from `Retry-After`.
- `openapi-typescript` types in `lib/api/schema.ts` via `npm run gen:api`.
- P5: `lib/api/sse.ts` — streaming with `fetch` + `ReadableStream` + `TextDecoder`
  (`EventSource` cannot send an `Authorization` header), parsing `event:`/`data:` lines,
  with `AbortController` cancellation.

### 7.6 Pages

**AuthPage** (P2) — Tabs for *Sign in* and *Create account*. Sign-up shows a six-segment
strength meter and a live rule checklist (8+ chars, upper, lower, number); the backend
enforces the same rules. Error banners use the API's error message. No magic link and no
forgot-password flow (ADR 0001): there is no email sending.

**DashboardPage** (P3) — Heading and a staggered, animated grid of five tool cards (GitHub,
Snippets, Notes, Timer, API Tester), each with an icon, description and, where relevant, a
count from `GET /dashboard/summary`.

**SnippetsPage** (P3) — Header with *Add Snippet*. Search (300 ms debounce) and tag chips
from `GET /snippets/tags`. Two-column animated card grid: title, language, code block,
tags; hover reveals copy (with a 2-second ✓), edit, delete, favourite. Create / edit modal
with title, description, language, comma-separated tags and code. Delete asks via
`ConfirmDialog`. Cursor pagination with *Load more*. Empty state with an icon.
P4: hybrid search bar with mode, filters and a match-type badge.
P5: *Explain* panel (streaming markdown, level selector, Stop button) and AI tag
suggestions as accept/dismiss chips.

**NotesPage** (P3) — Two panes. Left: search and a list sorted by last update, each with a
date and a hover delete. Right: title input and a Write/Preview toggle; preview renders
GitHub-flavoured markdown. Title and content auto-save 1 s after typing stops, with a
Saving…/Saved indicator. Empty state when nothing is selected.
P5: *Ask your notes* panel with streaming answers and clickable `[n]` citations.

**TimerPage** (P3) — Focus (25:00) and break (5:00) modes, start/pause and reset. When a
focus period ends it posts a completed session and switches to break; when a break ends it
returns to focus. Shows today's and all-time completed sessions.
P6: daily focus-minutes chart, current and best streak.

**GithubPage** (P6) — Username search (500 ms debounce) through the backend. Shows avatar,
name, bio, company, location, blog, followers, following and public repos, then the six
most recently updated repositories with description, language, stars and forks. Handles
not-found and rate-limit errors. Weekly insight card with *Generate now*.

**ApiTesterPage** (P6) — Method select (GET, POST, PUT, PATCH, DELETE), URL, headers as
JSON, and a body (disabled for GET and DELETE). Sent through the backend proxy. Shows
status (coloured by class), time in ms, headers, and a pretty-printed body. *Import cURL*
and *Explain this error* on 4xx/5xx.

**SettingsPage** (P2) — Read-only email; change password (current + new, same strength
meter and rules); **API connection** card (`ApiConnectionCard`) that calls `/api/v1/me`
and shows *Connected* with the user id and email, or the error code, message and request
id, with a *Re-check* button. P6: GitHub username field.

**Everywhere** (P5): an AI usage indicator ("12/50 AI requests left today"), and loading,
empty, error and rate-limited states on every async view.

### 7.7 Design system (P2)

Dark only. Tailwind 4 theme tokens (`@theme` in `styles/index.css`):

| Token | Value | Use |
|---|---|---|
| `background` | `#0f172a` | page |
| `surface` | `#111827` | cards, sidebar |
| `border` | `#1f2937` | dividers |
| `text` | `#e5e7eb` | body text |
| `accent` | `#3b82f6` | primary actions, focus rings |

Fonts: **Inter** (UI) and **JetBrains Mono** (code). Component classes: `.card`,
`.btn-primary`, `.btn-secondary`, `.input-field`. Shared components: `Modal` (Escape
closes, body scroll lock, `aria-modal`, labelled title), `ConfirmDialog` (async confirm
with its own loading and error state), `PageLoader` / `FullPageLoader` (`role="status"`),
`AppLayout`. Merge classes with `cn()`.

**Accessibility is a requirement, not polish:** semantic HTML, keyboard reachability,
visible focus, labelled controls, `aria-live` on loading states. Keep it intact in every
new view.

---

## 8. Backend

### 8.1 Application (P1)

`app/main.py` → `create_app()`:

- Configures logging (JSON in production, console otherwise) and Sentry (only when
  `SENTRY_DSN` is set; `send_default_pii=False`).
- Middleware: `RequestContextMiddleware` (request id + access log) and CORS restricted to
  `CORS_ORIGINS`, exposing `X-Request-ID` and `Retry-After`.
- Exception handlers for `AppError`, Starlette HTTP errors, request validation, and a
  catch-all that logs the traceback and returns a generic 500.
- `/docs` is served only outside production. `/openapi.json` is always available for type
  generation.
- Lifespan logs startup (environment, CORS origins) and disposes the engine and Redis pool
  on shutdown.

### 8.2 Configuration (P1)

`core/config.py`: a `Settings` class read from the environment and `.env`, cached with
`get_settings()`. Secrets are `SecretStr`. Validation fails fast at startup:

- `DATABASE_URL` is normalised to `postgresql+asyncpg://` (Neon hands out `postgres://…?sslmode=require`).
- `JWT_SECRET` must be at least 32 bytes outside tests.
- Derived: `cors_origin_list`, `is_production`, `uses_transaction_pooler`.
- P4: at startup, assert the embedding provider's dimension equals `EMBEDDING_DIM`.

### 8.3 Authentication (P1)

See [ADR 0001](adr/0001-own-authentication.md) for the reasoning.

**Passwords.** argon2id via `argon2-cffi` with its default (RFC 9106) parameters. Rules,
enforced server-side: 8–128 characters with an uppercase letter, a lowercase letter and a
digit. On login, a hash made with outdated parameters is transparently re-hashed. For an
unknown email, login still runs one dummy verification so response time doesn't reveal
which accounts exist; both cases return 401 `INVALID_CREDENTIALS`.

**Access token.** HS256 JWT signed with `JWT_SECRET`, valid `ACCESS_TOKEN_TTL_MINUTES`
(default 15). Claims `sub` (user id), `iat`, `exp`, `iss = "devflow"`,
`aud = "devflow-api"`. Returned in the response body; the frontend keeps it in memory.

**Refresh token.** 32 random bytes (`secrets.token_urlsafe`), sent as the cookie
`devflow_refresh` — `HttpOnly`, `Secure` (configurable off only for plain-http local
development), `SameSite=Lax`, `Path=/api/v1/auth`, lifetime `REFRESH_TOKEN_TTL_DAYS`
(default 30). The database stores only its **SHA-256 hash** — a stolen database dump
yields no usable tokens.

- **Rotation:** every `/auth/refresh` revokes the presented token and issues a new one in
  the same `family_id`.
- **Reuse detection:** presenting an already-revoked token means it was copied; the whole
  family is revoked, signing out every device that descends from that login.
- **CSRF:** `/auth/refresh` and `/auth/logout` are the only cookie-authenticated routes.
  `SameSite=Lax` stops browsers from attaching the cookie to cross-site POSTs, and the
  API also rejects requests whose `Origin` is not in `CORS_ORIGINS`. Every other route
  reads a bearer header, which a cross-site form cannot set.

**`get_current_user()`** — the FastAPI dependency every protected route uses.

1. Read `Authorization: Bearer <token>`. Missing → 401 `MISSING_TOKEN`; wrong scheme or
   empty → 401 `MALFORMED_TOKEN`.
2. Verify signature with an explicit `algorithms=["HS256"]` (so `alg=none` and algorithm
   confusion are refused); require `exp`, `iat`, `sub`, `aud`, `iss`; check `aud` and
   `iss`.
3. Return `CurrentUser(id: UUID)`, the id from `sub`.

Error codes: `TOKEN_EXPIRED`, `INVALID_TOKEN`. The reason a signature failed is never
echoed to the caller.

**Trade-off Om should be able to state:** access tokens are stateless, so after a password
change or logout an already-issued access token keeps working until it expires (≤ 15 min).
Short lifetimes are what make that acceptable.

### 8.4 Errors (P1)

Every failure, deliberate or not, returns one shape:

```json
{ "error": { "code": "SNIPPET_NOT_FOUND", "message": "Snippet not found.",
             "details": {}, "request_id": "b6f1…" } }
```

`AppError` subclasses: `NotFoundError` (404), `UnauthorizedError` (401), `ConflictError`
(409), `ValidationFailedError` (422), `RateLimitedError` and `QuotaExceededError` (429 — a
`retry_after` in `details` becomes a `Retry-After` header), `UpstreamError` (502),
`ServiceUnavailableError` (503). FastAPI's validation errors and Starlette's 404/405 are
rewritten into the same shape. Stack traces never reach the client.

### 8.5 Observability (P1)

- `X-Request-ID` is read from the request (only if it matches a safe pattern) or
  generated, stored in a `ContextVar`, returned on the response, added to every log line
  and embedded in every error body.
- One access log per request: method, path, status, `duration_ms`. Passwords, tokens and
  cookies are never logged.
- `GET /health` — liveness; touches **nothing**, so a slow database cannot make the
  platform restart a healthy container.
- `GET /ready` — readiness; runs `SELECT 1` and a Redis `PING` in parallel with short
  timeouts, returning 503 `NOT_READY` with which dependency failed.

### 8.6 Database (P1)

- `db/session.py`: one cached async engine (`pool_size=5`, `max_overflow=5`,
  `pool_pre_ping`), `expire_on_commit=False`, a session per request with rollback on error.
- Neon offers a **pooled** host (`…-pooler.…`, PgBouncer in transaction mode) and a
  **direct** host. When the URL is pooled, asyncpg's prepared-statement cache is disabled —
  otherwise statements prepared on one pooled backend fail on another.
- The API and worker use `DATABASE_URL` (pooled in production); **Alembic uses
  `DATABASE_DIRECT_URL`**, never the transaction pooler, because migrations need session
  features such as advisory locks.

### 8.7 Migrations (P1)

- Alembic, async `env.py`, one migration per schema change, date-prefixed file names.
- Fresh databases (local, CI, Neon) run `alembic upgrade head`; production runs it on
  deploy.
- Show Om the SQL of every new migration (`alembic upgrade head --sql`) before applying
  it. Never drop or rewrite user data without asking.

### 8.8 Rate limiting and quotas

- P1: a Redis-backed limiter behind a `RateLimiter` protocol. Auth routes: login 10/min per
  IP and 5/min per email, register 5/hour per IP.
- P5: upgraded to a sliding window used as a dependency, keyed by user id (IP for
  unauthenticated routes). Defaults: **120/min** general, **10/min** AI routes, **30/min**
  API-tester proxy.
- P5: daily AI quota per user (`AI_DAILY_QUOTA_PER_USER`, default 50), counted in
  `ai_usage`.
- 429 with `Retry-After` and the standard error body. Check limits and quota **before** a
  stream starts.

### 8.9 AI layer (P4–P5)

**LLM provider** (`services/ai/llm.py`):

```python
class LLMProvider(Protocol):
    name: str
    model: str
    async def generate_structured(self, messages: list[Message], schema: type[T], *,
                                  temperature: float = 0.2) -> LLMResult[T]: ...
    async def stream(self, messages: list[Message], *,
                     temperature: float = 0.3) -> AsyncIterator[StreamChunk]: ...
```

Implementations: Gemini (default, plain httpx against the REST API), an OpenAI-compatible
provider (for Ollama/vLLM later), and `FakeLLMProvider`. `LLMResult` carries the parsed
object plus tokens, latency and cost. Timeouts and retries with backoff on transient
upstream errors (5xx, 429 with a short `Retry-After`). Prompts are **versioned templates**
(`prompts/explain_code_v1`, …) and the version is logged with every call.

**Embeddings** (`services/ai/embeddings.py`): `EmbeddingProvider` protocol with
`embed(texts) -> list[list[float]]`, `dim`, `model_name`. `FastEmbedProvider` runs in
`asyncio.to_thread` and loads the model once per process; `FakeEmbeddingProvider` returns
deterministic hash-based vectors for tests. The model is downloaded at **Docker build
time**.

**Redaction** (`services/ai/redaction.py`): before *any* text leaves for an LLM, replace
likely secrets — AWS keys, GitHub tokens, private-key blocks, JWTs, Stripe keys,
`api_key=`/`password=` assignments — with `[REDACTED]`. Every pattern unit-tested.

**Usage** (`services/ai/usage.py`): record an `ai_usage` row for every call, success or
failure, with cost from a per-model price table in config.

### 8.10 Background jobs (P4)

Taskiq ([ADR 0003](adr/0003-taskiq-for-background-jobs.md)): a Redis broker
(`taskiq-redis`), a **worker** process and a **scheduler** process, all from the API's
image and environment (`workers/broker.py`, `workers/tasks.py`, `workers/schedules.py`).
Tasks: `embed_snippet`, `embed_note`, `backfill_embeddings` (batches of 32),
`weekly_insights` (cron, Mondays 06:00 IST). Exactly **one** scheduler runs, or every
cron job would fire twice.

Jobs are enqueued **after** the transaction commits — otherwise the worker can pick up a
job for a row it cannot see yet. Transient failures retry with backoff up to 3 times; the
final failure sets `embedding_status = 'failed'`. The dispatcher sits behind a protocol so
tests record jobs instead of queuing them.

---

## 9. API reference

All application routes live under `/api/v1`, require a bearer token unless marked public,
and use the error format in 8.4. Lists use cursor pagination:
`?limit=20&cursor=<opaque>` → `{ "items": [...], "next_cursor": "..." | null }`.

### Infrastructure

| Method | Path | Notes | Phase |
|---|---|---|---|
| GET | `/health` | public, liveness | P1 |
| GET | `/ready` | public, Postgres + Redis | P1 |

### Auth

| Method | Path | Notes | Phase |
|---|---|---|---|
| POST | `/auth/register` | public; `{ email, password }` → 201 `{ access_token, expires_in, user }` + refresh cookie; 409 `EMAIL_TAKEN` | P1 |
| POST | `/auth/login` | public; same response; 401 `INVALID_CREDENTIALS` | P1 |
| POST | `/auth/refresh` | cookie; rotates the refresh token; 401 `INVALID_REFRESH_TOKEN` | P1 |
| POST | `/auth/logout` | cookie; revokes this device's token, clears the cookie; 204 | P1 |

### Account

| Method | Path | Notes | Phase |
|---|---|---|---|
| GET | `/me` | `{ id, email, github_username, created_at }` | P1 |
| POST | `/me/password` | `{ current_password, new_password }`; revokes every other session | P1 |
| PATCH | `/me` | set `github_username` | P6 |
| GET | `/dashboard/summary` | counts of snippets, notes, focus sessions | P3 |

### Snippets

| Method | Path | Notes | Phase |
|---|---|---|---|
| GET | `/snippets` | filters `q`, `language`, `tag`, `favorite`; paginated | P3 |
| GET | `/snippets/tags` | distinct tags with counts, for the filter chips | P3 |
| POST | `/snippets` | create (P4: then enqueue `embed_snippet`) | P3 |
| GET / PATCH / DELETE | `/snippets/{id}` | P4: PATCH re-embeds only if the content hash changed | P3 |
| GET | `/snippets/search?q=&mode=hybrid&language=&tag=&limit=10` | `mode` = `keyword` \| `semantic` \| `hybrid`; items carry `score` and `match_type` | P4 |
| POST | `/snippets/{id}/ai/tags` | suggested `language`, `tags[]`, `description`; never overwrites user tags | P5 |
| POST | `/snippets/{id}/ai/explain` | **SSE**; body `{ level: beginner \| intermediate \| expert }` | P5 |

### Notes

| Method | Path | Notes | Phase |
|---|---|---|---|
| GET / POST | `/notes` | P5: create enqueues `embed_note` | P3 |
| GET / PATCH / DELETE | `/notes/{id}` | P5: edits re-chunk and re-embed only changed chunks | P3 |
| POST | `/notes/ask` | `{ question }` → **SSE**: `sources`, then `token`s, then `done` | P5 |

### Pomodoro

| Method | Path | Notes | Phase |
|---|---|---|---|
| POST | `/pomodoro/sessions` | record a completed focus session `{ duration_seconds }`; the server stamps the time | P3 |
| GET | `/pomodoro/sessions` | paginated | P3 |
| GET | `/pomodoro/stats?range=7d\|30d&tz=` | daily minutes, totals, current and best streak | P6 |

### API tester

| Method | Path | Notes | Phase |
|---|---|---|---|
| POST | `/api-tester/send` | server-side proxy with SSRF protection | P6 |
| POST | `/api-tester/parse-curl` | deterministic → `{ method, url, headers, body }` | P6 |
| POST | `/api-tester/explain-error` | `likely_causes[]`, `suggested_fixes[]`, `confidence` | P6 |

### GitHub

| Method | Path | Notes | Phase |
|---|---|---|---|
| GET | `/github/overview?username=` | server token, 15-min Redis cache, ETag conditional requests | P6 |
| GET | `/github/insights?limit=4` | stored weekly insights | P6 |
| POST | `/github/insights/generate` | on demand for the current week; counts against the AI quota | P6 |

Every endpoint has typed request and response models, so `openapi-typescript` produces
accurate frontend types.

### SSE event format

```
event: token    data: {"text": "..."}
event: sources  data: [{"n": 1, "note_id": "...", "note_title": "...", "heading": "...", "excerpt": "..."}]
event: done     data: {"usage": {"input_tokens": 0, "output_tokens": 0}, "latency_ms": 0}
event: error    data: {"code": "...", "message": "..."}
```

If the client disconnects, stop streaming and cancel the upstream LLM request.

---

## 10. Data model

All tables live in the `public` schema and are created by Alembic. Every user-owned table
has `user_id uuid not null references users on delete cascade` and an index on `user_id`.
`updated_at` is maintained by the application on every update.

| Table | Columns | Phase |
|---|---|---|
| `users` | `id uuid pk`, `email citext unique`, `password_hash text`, `github_username text null`, `created_at`, `updated_at` | P1 |
| `refresh_tokens` | `id uuid pk`, `user_id`, `token_hash text unique`, `family_id uuid`, `expires_at`, `revoked_at null`, `replaced_by_id null`, `created_at`; index on `family_id` | P1 |
| `snippets` | `id uuid pk`, `user_id`, `title text`, `description text null`, `code text`, `language text null`, `tags text[] default '{}'`, `favorite boolean default false`, `created_at`, `updated_at` | P3 |
| `notes` | `id uuid pk`, `user_id`, `title text`, `content text`, `created_at`, `updated_at` | P3 |
| `pomodoro_sessions` | `id uuid pk`, `user_id`, `completed_at timestamptz`, `duration_seconds int check (> 0)`, `created_at`; index `(user_id, completed_at)` | P3 |

**Snippets search columns (P4)** — `content_hash text`; `embedding vector(384)`;
`embedding_status text not null default 'pending'` in (`pending`, `ready`, `failed`);
`embedded_at timestamptz`; `ai_tags text[]`, `ai_description text`, `ai_language text`;
`search_tsv tsvector` **generated always … stored**, weighted title (A), description (B),
tags (B), code (C, `simple` config). Indexes: HNSW on `embedding` (`vector_cosine_ops`),
GIN on `search_tsv`.

**`note_chunks` (P5)** — `id`, `note_id → notes on delete cascade`, `user_id`,
`chunk_index`, `heading`, `content`, `content_hash`, `token_count`, `embedding vector(384)`,
generated `search_tsv`, `created_at`, `unique(note_id, chunk_index)`; HNSW, GIN and
`user_id` indexes.

**`ai_usage` (P5)** — `id`, `user_id`, `feature` (`explain_code` | `auto_tag` |
`ask_notes` | `explain_http_error` | `github_insights`), `provider`, `model`,
`input_tokens`, `output_tokens`, `cost_usd numeric(10,6)`, `latency_ms`, `status`
(`success` | `error` | `quota_exceeded`), `error_code`, `created_at`; index
`(user_id, created_at)`.

**`github_insights` (P6)** — `id`, `user_id`, `github_username`, `week_start date`,
`stats jsonb`, `summary jsonb`, `created_at`, `unique(user_id, week_start)`.

---

## 11. Features in depth

### 11.1 Embedding pipeline (P4)

- Snippet embedding text: `title + description + user tags + language + code`, truncated
  to the model's 512-token limit.
- **Idempotency:** hash the embedding text; if the hash is unchanged and status is
  `ready`, skip. This is what makes a 1-second notes autosave harmless.
- Always in the worker, never inside the request. `backfill_embeddings` covers rows that
  were created before the pipeline existed or whose embedding failed.

### 11.2 Hybrid search (P4)

One SQL query with CTEs, always scoped to `user_id` and the filters:

1. **Keyword:** `websearch_to_tsquery('english', :q)` against `search_tsv`, ranked by
   `ts_rank_cd`, top 50.
2. **Semantic:** embed the query (cached in Redis by query hash, 1 h), order by
   `embedding <=> :qvec`, top 50, only `embedding_status = 'ready'`.
3. **Fusion:** `score = Σ 1 / (60 + rank)` across branches; return the top `limit`.

`match_type` is `keyword`, `semantic` or `both`. `mode=keyword|semantic` return one branch,
which the evaluation needs. Comment in the code why RRF beats adding raw scores.

### 11.3 Explain this code (P5)

Redact → versioned prompt → stream tokens as SSE. Quota and rate limit checked first;
`ai_usage` recorded on completion and on error; upstream cancelled on disconnect.

### 11.4 Auto-tagging (P5)

```python
class SnippetTagSuggestion(BaseModel):
    language: str        # normalised, lowercase
    tags: list[str]      # 3-5 lowercase kebab-case
    description: str     # one sentence, max 140 chars
```

Validate with Pydantic; on failure retry **once** with the validation error in the prompt,
then return a clean error. Normalise (lowercase, dedupe, max 5). The user accepts
suggestions explicitly; user tags are never overwritten.

### 11.5 Ask your notes (P5)

- **Chunking:** split by markdown heading, then ~300-token windows with ~50 overlap;
  keep the nearest heading for citations.
- **Re-embedding:** compare chunk hashes; embed new or changed chunks only, delete removed.
- **Retrieval:** hybrid search over `note_chunks`, top 6.
- **Guardrail:** if the best semantic similarity is under a configurable threshold, answer
  "I couldn't find this in your notes" **without calling the LLM**.
- **Generation:** numbered sources; the model must cite `[n]` and answer only from them.

### 11.6 API tester proxy (P6)

SSRF protection, all tested:

- `http`/`https` only.
- Resolve the hostname **first**; block private, loopback, link-local, multicast, reserved
  and unspecified ranges (IPv4 and IPv6), including `169.254.169.254`. Connect to the
  validated IP (defeats DNS rebinding) while sending the original `Host`/SNI.
- At most 3 redirects, **each hop re-validated**.
- 15 s timeout, 2 MB body cap (truncate and flag), hop-by-hop headers stripped.
- Returns `{ status, status_text, headers, body, body_truncated, elapsed_ms, size_bytes }`.

`parse-curl` is deterministic (`shlex`): `-X`, `-H`, `-d`/`--data`/`--data-raw`, `--json`,
`-u`, quoting, line continuations. **Use AI only where rules can't do the job.**

### 11.7 Pomodoro stats (P6)

In SQL (`date_trunc`, window functions) in the user's timezone (`tz`, default
`Asia/Kolkata`). Unit-test streaks across gaps, multiple sessions a day, and midnight in
other timezones.

### 11.8 GitHub overview and weekly insights (P6)

Server-side calls with `GITHUB_TOKEN` (5,000 req/h instead of 60), 15-minute Redis cache,
stored ETags with `If-None-Match` (304s don't count against the limit), and a clear
`GITHUB_RATE_LIMITED` error with the reset time. The weekly cron aggregates last week's
activity per user and asks for:

```python
class WeeklyInsight(BaseModel):
    headline: str
    highlights: list[str]   # 2-4
    suggestions: list[str]  # 1-3
```

Upsert on `(user_id, week_start)` so re-runs are idempotent.

---

## 12. Security

| Control | Where | Phase |
|---|---|---|
| Passwords hashed with argon2id; never logged or returned | `core/passwords.py` | P1 |
| Login timing does not reveal whether an email exists | auth service | P1 |
| Access JWT: explicit algorithm, `exp`, `aud`, `iss` checked | `core/security.py` | P1 |
| Refresh tokens stored hashed, rotated on use, family revoked on reuse | auth service | P1 |
| Refresh cookie `HttpOnly`, `Secure`, `SameSite=Lax`, path-scoped; `Origin` checked | auth routes | P1 |
| Rate limits on login and register | limiter | P1 |
| Identity from the token's `sub`, never from the request body | every route | P1 |
| Every query filtered by `user_id`; cross-user → 404 | repositories | P3 |
| IDOR tests for every resource | tests | P3 |
| CORS restricted to `CORS_ORIGINS` | `main.py` | P1 |
| No stack traces or internal messages to clients | error handlers | P1 |
| Non-root container | Dockerfile | P1 |
| Secret redaction before any LLM call | `redaction.py` | P5 |
| Rate limits and daily AI quota | limiter | P5 |
| SSRF protection on the proxy | `api_tester.py` | P6 |
| Request body size limits | middleware / Caddy | P7 |
| CSP and security headers on the frontend | `vercel.json` | P7 |
| Bound parameters only — never string-formatted SQL | everywhere | always |
| `pip-audit` and `npm audit` in CI | CI | P0 |

**Secrets:** nothing secret may ever carry a `VITE_` prefix — it would be inlined into the
JavaScript. `JWT_SECRET` rotates by redeploying; doing so signs everyone out of their
current access token but not their refresh sessions.

---

## 13. Testing and evaluation

- Tests never contact a paid or external API: LLMs, embeddings and GitHub are faked
  (fake providers, respx). The auth tests mint their own tokens with the test secret, so
  the real verification path runs against tokens the tests control.
- Integration tests run against real Postgres (pgvector image) and Redis — locally via
  Docker Compose, in CI via service containers.

### Required as phases land

- P1: every way an access token can be wrong (missing, malformed, expired, wrong
  audience, wrong issuer, bad signature, `alg=none`, each required claim dropped,
  non-UUID subject); register/login/refresh/logout; refresh rotation and reuse detection;
  password change revoking other sessions; login rate limit → 429 with `Retry-After`;
  error shape and request ids; `/health`, `/ready` and `/ready` returning 503.
- P2: base query token attachment, refresh-and-retry, one shared refresh under concurrent
  401s, sign-out on failed refresh, no refresh on non-401 errors; `toApiError` mapping.
- P3: CRUD for snippets, notes, sessions; **IDOR — cross-user access to every resource
  type returns 404**; pagination cursors.
- P4: search ranking with deterministic fake embeddings (keyword-only, semantic-only,
  both); embedding idempotency.
- P5: rate limiter and quota → 429 with `Retry-After`; every redaction pattern; SSE event
  format and the error event; the SSE parser with chunks split mid-line.
- P6: SSRF cases (private IPs, localhost, metadata IP, IPv6 loopback, redirect to a
  private IP, non-http scheme); cURL parser cases; pomodoro streak edge cases.
- **≥ 80% coverage** on `services/` and `repositories/` from P3.

### Search evaluation (P7)

`evals/search/`: ~60 realistic snippets (JS/TS/Python/SQL/CSS), 30 queries in
`queries.yaml` with expected ids — including ones keywords fail on ("stop a function from
firing too often" → debounce). Report **Recall@5**, **MRR@10** and p50/p95 latency for
keyword, semantic and hybrid; write timestamped JSON and a Markdown table for the README.

---

## 14. Running, building, deploying

### Local

```bash
docker compose up -d                                   # Postgres on 5434, Redis on 6380
cd backend && cp -n .env.example .env                  # -n: never overwrite an existing .env
uv run alembic upgrade head && uv run uvicorn app.main:app --reload   # API on :8000 (P1+)
cd frontend && npm install && npm run dev              # app on :5173, /api proxied to :8000
```

The API and the frontend each need their own terminal.

### Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

### CI

GitHub Actions on every push to `main`, every PR and weekly. **Backend:** uv sync, ruff,
ruff format, mypy, (P1+) `alembic upgrade head`, pytest with coverage against Postgres and
Redis service containers, `pip-audit`. **Frontend:** `npm ci`, lint, typecheck, Vitest,
build, `npm audit`. CI holds no real credentials.

### Deployment (P7)

- **Frontend** — Vercel, Root Directory `frontend`, a rewrite of `/api/*` to the API's
  hostname, and an SPA fallback.
- **Backend** — `deploy/oracle/`: api, worker and scheduler from one image, plus Redis,
  on the Oracle Always Free VM that also runs ReviewPilot. One shared Caddy terminates TLS
  for both apps. Migrations run with `DATABASE_DIRECT_URL` on deploy; embeddings are
  backfilled after the first deploy.
- **Database** — Neon, with `CREATE EXTENSION vector` in the P4 migration.

### Environment variables

| Frontend | Backend |
|---|---|
| none required (same-origin `/api`) | `APP_ENV`, `LOG_LEVEL` |
| | `DATABASE_URL`, `DATABASE_DIRECT_URL`, `REDIS_URL` |
| | `JWT_SECRET`, `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS`, `COOKIE_SECURE` |
| | `CORS_ORIGINS` |
| | `LLM_PROVIDER`, `LLM_MODEL`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` |
| | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` |
| | `GITHUB_TOKEN`, `AI_DAILY_QUOTA_PER_USER`, `SENTRY_DSN` |

`backend/.env.example` lists every variable with a comment saying what it is and whether
it is secret.

---

## 15. Phases and acceptance criteria

| Phase | Done when |
|---|---|
| **0 Scaffold** | Spec and ADRs reflect the rebuild decisions; `docker compose up -d` is healthy; the empty backend and frontend pass every check; CI green |
| **1 Backend + auth** | A script can register, log in, refresh, call `/me`, change the password and log out; the auth test suite passes; CI green |
| **2 Frontend shell** | In the browser: create an account, reload and stay signed in, see *Connected* on Settings, change the password, sign out |
| **3 CRUD** | Snippets, notes, timer and dashboard work end to end through the API; IDOR tests pass; ≥ 80% coverage on services and repositories |
| **4 Search** | An intent-style query finds a snippet keyword search misses; existing snippets are backfilled |
| **5 AI** | Explain, auto-tag and Ask your notes work in the UI; `ai_usage` rows record cost; quota and limits return 429 |
| **6 Proxy, stats, GitHub** | The tester reaches APIs that fail on browser CORS; SSRF tests pass; insights generate and display |
| **7 Eval & deploy** | Evaluation table exists; production frontend, API, worker and scheduler run; README matches what shipped |

---

## 16. Non-negotiables

- Do not let any query reach user data without a `user_id` filter.
- Do not trust a `user_id` from the request body — identity comes from the token.
- Do not store a password or refresh token in plaintext, or log either.
- Do not put a secret in a `VITE_` variable or in git.
- Do not run embeddings or LLM calls inside a request, except the two streaming endpoints.
- Do not send unredacted user content to an LLM.
- Do not format SQL with strings.
- Do not add a dependency without saying why.
- Do not drop or rewrite user data without asking; show migration SQL first.
- Do not move to the next phase without Om's confirmation.

---

## 17. Open questions

| Question | Blocks |
|---|---|
| Does SSE stream cleanly through Vercel's external rewrite, or does the API need its own subdomain on a shared site? | P5 testing, P7 deploy |
| VM shape and free RAM (Ampere A1 or E2 micro) — sets memory limits for the worker and the embedding model | P7 |
| API hostname for Let's Encrypt | P7 |
| Reuse the old Vercel project or create a new one? | P7 |
| Add the OpenAI-compatible provider in P5, or later? | P5 |
