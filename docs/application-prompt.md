# DevFlow — Application Prompt

A complete description of DevFlow, frontend and backend, for anyone — human or AI agent —
who needs to understand, extend, or rebuild it. Paste this whole file as the opening
context of a working session.

**Status markers used throughout:**
✅ built and running · 🟡 partly built · ⏳ planned, not built yet

> **How this relates to the other docs.** This file is the single-read overview. Where
> it summarises, the linked document is authoritative:
> [fullstack-upgrade-prompt.md](fullstack-upgrade-prompt.md) for the target design,
> [AUDIT.md](AUDIT.md) for what the code actually does today,
> [environment.md](environment.md) for configuration, [adr/](adr/README.md) for why.
> If this file and the code disagree, the code wins — and this file should be fixed.

---

## 1. Your role

You are a senior full-stack engineer working with **Om**, a frontend developer moving into
Python/AI full-stack roles. DevFlow is a resume project: Om must be able to explain and
defend every decision in an interview. That shapes how you work:

1. **Work in phases** (Section 15). Never start the next phase until Om confirms the
   current one is done.
2. **End every phase with:** files changed, exact commands to verify locally, the key
   concepts explained simply, and three interview questions with strong model answers.
3. **Never break existing features.** The app is live on Vercel. Migrate one module at a
   time; the app must work after every phase.
4. **Check the code before asking; ask before assuming.** Do not invent tables, columns,
   APIs, or library behaviour. If unsure how Supabase, GitHub, or a library behaves, say
   so and check the official docs.
5. **Tests are part of the work,** not a follow-up.
6. **No secrets in code or git.** Everything comes from environment variables.
7. **Prefer boring, explainable solutions.** Every new dependency needs a reason Om can
   repeat.

---

## 2. What DevFlow is

A developer productivity dashboard. One signed-in user keeps their own:

| Module | What it does | Route |
|---|---|---|
| **Dashboard** | Tiles linking to each tool, with counts of snippets, notes and focus sessions | `/` |
| **Snippet Manager** | Save, edit, delete, copy, search and tag-filter code snippets | `/snippets` |
| **Markdown Notes** | Notes with a live preview and debounced auto-save | `/notes` |
| **Focus Timer** | A 25-minute focus / 5-minute break Pomodoro timer that counts completed sessions | `/timer` |
| **GitHub Analytics** | Look up any public GitHub user: profile and six most recent repositories | `/github` |
| **HTTP API Tester** | Compose and send an HTTP request, inspect status, timing, headers and body | `/api` |
| **Settings** | Account email, password change, and an API connection check | `/settings` |

The upgrade adds a Python backend and AI features on top: hybrid semantic search over
snippets, streaming "explain this code", AI tag suggestions, "ask your notes" with
citations, a server-side API tester with SSRF protection, Pomodoro statistics, and weekly
GitHub insights.

---

## 3. Current status

| Phase | Scope | Status |
|---|---|---|
| — | Repository restructured into `frontend/` + `backend/` + `db/` + `docs/` | ✅ |
| 0 | Audit of the existing app ([AUDIT.md](AUDIT.md)) | ✅ approved |
| 1 | Backend foundation: FastAPI, JWT verification, `/health`, `/ready`, `/api/v1/me`, Alembic baseline, Docker, CI, frontend API client | ✅ merged — **not signed off** (see below) |
| 2 | Snippets, notes and pomodoro CRUD move behind the API | ⏳ |
| 3 | pgvector, embeddings, ARQ worker, hybrid search | ⏳ |
| 4 | LLM features: explain, auto-tag, ask your notes; quotas and rate limits | ⏳ |
| 5 | API tester proxy, pomodoro stats, GitHub overview and insights | ⏳ |
| 6 | Search evaluation, hardening, production deployment | ⏳ |

**Blocking Phase 1 sign-off:** the Supabase project the app was configured for
(`sgkffektowuklgrywigx`) no longer resolves — public DNS returns NXDOMAIN. Sign-in fails
locally and in production. A new Supabase project must be created and seeded from
[db/migrations/20260407000000_init_tables.sql](../db/migrations/20260407000000_init_tables.sql),
its URL and anon key placed in `frontend/.env`, `backend/.env` and Vercel, and then
`GET /api/v1/me` confirmed from the Settings page against a real session.

**Still open from the audit:** whether the project signs tokens with JWKS (asymmetric keys)
or the legacy HS256 secret. A new project will almost certainly use JWKS, which is the
backend's default mode.

---

## 4. Architecture

### Today

```
Browser (React on Vercel)
  ├── supabase-js ──────────► Supabase Auth       (sign-in, sessions)
  ├── supabase-js ──────────► Supabase Postgres   (snippets, notes, user_stats — RLS-protected)
  ├── fetch ────────────────► api.github.com       (unauthenticated, 60 req/h)
  ├── fetch ────────────────► any URL               (API tester, subject to browser CORS)
  └── RTK Query + JWT ──────► FastAPI  /api/v1/me   (Phase 1: proves the auth chain)
```

### Target

```
                 ┌──────────────────────── Supabase ────────────────────────┐
                 │  Auth (issues JWTs)        Postgres + pgvector, RLS on    │
                 └──────▲─────────────────────────────────▲─────────────────┘
                        │ sign-in / session               │ SQLAlchemy + asyncpg
┌───────────────────────┴──┐   HTTPS + Bearer JWT   ┌─────┴──────────────────────┐
│ React + TS + RTK Query   │ ─────────────────────► │ FastAPI (api)               │
│ (Vercel)                 │ ◄──── JSON / SSE ───── │  verifies JWT · scopes by   │
└──────────────────────────┘                        │  user_id · rate limits      │
                                                    └──┬──────────────┬───────────┘
                                                       │ enqueue      │ LLM / GitHub
                                                  ┌────▼────┐         ▼
                                                  │  Redis  │    external APIs
                                                  └────┬────┘
                                                  ┌────▼─────────────────────┐
                                                  │ ARQ worker               │
                                                  │  embeddings · insights   │
                                                  └──────────────────────────┘
```

### Decisions that shape everything (see [adr/](adr/README.md))

| # | Decision | The one-line reason |
|---|---|---|
| 0001 | Keep Supabase Auth; the API **verifies** its JWTs | Login already works in production; rebuilding it risks users for no gain |
| 0002 | API authorizes every query by `user_id`; RLS stays on | The API's DB role bypasses RLS, so RLS can't be the control — but it's free defence in depth |
| 0003 | ARQ, not Celery | The backend is fully async; ARQ is async-native and small |
| 0004 | FastEmbed `bge-small-en-v1.5` locally | Free, 384 dims, ONNX so no PyTorch in the image |
| 0005 | Reciprocal Rank Fusion for hybrid search | Keyword and vector scores live on different scales; ranks don't |
| 0006 | API tester proxied server-side | Removes browser CORS limits — and makes SSRF protection mandatory |
| 0007 | Monorepo split by deployable | Two languages, two toolchains, two deploy targets |

---

## 5. Tech stack

### Frontend

| Concern | Choice | Status |
|---|---|---|
| Build | Vite 6 | ✅ |
| UI | React 18 + TypeScript 5.8 | ✅ |
| Styling | Tailwind CSS 3 + `@tailwindcss/typography` | ✅ |
| Routing | React Router 7, every route lazy-loaded | ✅ |
| Client state | Redux Toolkit | ✅ |
| Server state | RTK Query (backend) · React Query (GitHub page only, until Phase 5) | 🟡 |
| Auth | `@supabase/supabase-js` | ✅ |
| Markdown | `react-markdown` + `remark-gfm`, sanitised with DOMPurify | ✅ |
| Motion / icons / dates | framer-motion · lucide-react · date-fns | ✅ |
| Tests | Vitest + Testing Library + jsdom | ✅ |
| API types | `openapi-typescript` generated from the FastAPI schema | ⏳ Phase 2 |

### Backend

| Concern | Choice | Status |
|---|---|---|
| Language / packaging | Python 3.12, `uv` with a lockfile | ✅ |
| Framework | FastAPI | ✅ |
| Settings / validation | Pydantic v2, `pydantic-settings` | ✅ |
| Database | SQLAlchemy 2.0 async + `asyncpg`, Alembic | ✅ |
| Auth | PyJWT with JWKS support | ✅ |
| Cache / queue / limits | Redis | ✅ connection · ⏳ usage |
| Logging / errors | structlog (JSON in production) · Sentry when `SENTRY_DSN` is set | ✅ |
| Quality | Ruff (lint + format), mypy `--strict` | ✅ |
| Tests | pytest, pytest-asyncio, httpx `AsyncClient`, respx | ✅ |
| Background jobs | ARQ | ⏳ Phase 3 |
| Vectors / embeddings | pgvector, FastEmbed | ⏳ Phase 3 |
| LLM | provider interface; Gemini default; Anthropic/OpenAI swappable; fake for tests | ⏳ Phase 4 |

### Infrastructure

| Concern | Choice | Status |
|---|---|---|
| Frontend hosting | Vercel, Root Directory = `frontend` | ✅ |
| Local stack | Docker Compose: pgvector Postgres (host port **5434**), Redis, API | ✅ |
| CI | GitHub Actions: backend + frontend jobs | ✅ |
| API + worker hosting | Render (or Railway / Fly.io) | ⏳ Phase 6 |
| Managed Redis | Upstash | ⏳ Phase 6 |

---

## 6. Repository structure

```
devflow/
├── frontend/                 React app — Vercel deploys this folder
│   ├── src/
│   │   ├── main.tsx          Entry: checks config, then loads the app
│   │   ├── app/              App shell, providers, route table, ConfigError, Redux store
│   │   ├── pages/            One component per route; composition only
│   │   ├── features/<name>/  api/ (data access) · store/ (slice) · hooks/ · lib/ · types.ts · index.ts
│   │   ├── components/       ui/ (Modal, ConfirmDialog, loaders, ApiConnectionCard) · layout/ (AppLayout)
│   │   ├── lib/              supabase/ client · api/ RTK Query · env.ts · utils/cn.ts
│   │   ├── hooks/ styles/ types/ test/
│   ├── vite.config.ts  vercel.json  package.json  .env.example
├── backend/                  FastAPI service
│   ├── app/
│   │   ├── main.py           App factory: middleware, routers, handlers, lifespan
│   │   ├── core/             config · security · errors · logging · middleware · redis
│   │   ├── db/               async engine, per-request session, declarative Base
│   │   ├── api/v1/routes/    health.py · me.py
│   │   ├── schemas/          Pydantic request/response models
│   │   ├── models/ repositories/ services/ workers/     ⏳ filled from Phase 2
│   ├── alembic/versions/     0001_baseline mirrors the live schema
│   ├── scripts/auth_stub.sql Stand-in for Supabase's auth schema on plain Postgres
│   ├── tests/unit/ tests/integration/
│   ├── Dockerfile  pyproject.toml  uv.lock  .env.example
├── db/
│   ├── migrations/           Canonical Supabase schema
│   └── archive/              Drifted manual scripts — never run
├── docs/                     This file, audit, architecture, environment, ADRs
├── docker-compose.yml
├── .github/workflows/ci.yml
└── AGENTS.md  llms.txt  README.md
```

### Rules

**Frontend**

- Imports use the `@/` alias, never `../../`.
- **Pages compose; features decide.** Pages render and dispatch. Logic and data access
  belong to a feature.
- **Every data call lives in `features/<name>/api/`.** Nothing else imports the Supabase
  client for data. Migrating a module to the API means rewriting that one file.
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

### 7.1 Boot sequence ✅

1. `main.tsx` calls `missingEnvVars()`. If `VITE_SUPABASE_URL` or `VITE_SUPABASE_ANON_KEY`
   is absent, it renders **`ConfigError`** naming the missing variables and stops. The app
   is imported dynamically *after* this check because importing it eagerly would evaluate
   the Supabase client, which throws before React can mount — the cause of a past blank
   production page.
2. Otherwise it renders `<AppProviders>` (Redux store + React Query client) around `<App>`.
3. `App` mounts `useAuthSession()`, which calls `supabase.auth.getSession()` once and
   subscribes to `onAuthStateChange`, keeping Redux `auth.user` in sync.
4. While `auth.isLoading` is true, a full-page spinner shows.
5. **Signed out** → only `AuthPage` renders. No route is mounted.
   **Signed in** → `AppLayout` wraps `AppRoutes`.

### 7.2 Routing ✅

Defined in `app/routes.tsx`, every page `React.lazy`-loaded so each is its own chunk.
Unknown paths redirect to `/`. `/auth/callback` exists but only mounts once a session
exists (known issue R5 in the audit: an email-link error in the URL hash is never shown).

### 7.3 Layout ✅

`AppLayout`: a fixed sidebar on desktop, a slide-in drawer with an overlay on mobile, a
"skip to main content" link, `aria-current` on the active link, the signed-in email and a
Sign Out button. Navigation items: Dashboard, GitHub Analytics, Snippets, Notes, Timer,
API Tester, Settings.

### 7.4 State ✅

| Slice | State | Thunks |
|---|---|---|
| `auth` | `{ user, isAuthenticated, isLoading }` | none — `setUser`, `setLoading` reducers |
| `snippets` | `{ snippets: Snippet[], status, error }` | `fetchSnippets`, `addSnippet`, `updateSnippet`, `deleteSnippet` |
| `notes` | `{ notes: Note[], activeNoteId, status, error }` | `fetchNotes`, `addNote`, `updateNote`, `deleteNote` + `setActiveNote` |
| `timer` | `{ completedSessions, status }` | `fetchStats`, `addCompletedSession`, `resetSessions` |
| `api` | RTK Query cache | `getMe` |

Collections are **plain arrays**, not normalized maps. Each page fetches its own data when
its slice's `status === 'idle'`. Only fetches record `pending`/`rejected`; failed
creates/updates/deletes are currently silent.

### 7.5 Data access

**Supabase modules** (✅ today, ⏳ replaced in Phase 2): `snippetsApi`, `notesApi`,
`timerApi` in `features/*/api/`. They map snake_case rows to camelCase types. Writes stamp
`user_id` from `requireUserId()` (`lib/supabase/session.ts`), which calls
`supabase.auth.getUser()`. Updates and deletes filter by `id` only — ownership is enforced
entirely by RLS.

**Auth** (✅, stays on Supabase permanently): `authApi` in `features/auth/api/` wraps
`getSession`, `onAuthStateChange`, `signInWithPassword`, `signUp`, `sendEmailLink`
(magic link *and* forgot-password), `updatePassword`, `signOut`.

**Backend client** (✅ Phase 1) in `lib/api/`:

- `createApi` with one base query, `reducerPath: 'api'`, and `tagTypes` for `Me`,
  `Snippet`, `Note`, `PomodoroSession` already declared.
- The base query reads `supabase.auth.getSession()` **per request** — never a cached
  token, because supabase-js refreshes in the background — and sets
  `Authorization: Bearer <access_token>`. Base URL: `VITE_API_URL` (default
  `http://localhost:8000`) + `/api/v1`.
- **On 401:** refresh the session once and retry. If the refresh fails, sign out.
  Concurrent 401s share **one** refresh promise so they cannot race.
- `toApiError()` maps every failure — backend error bodies, dropped connections
  (`FETCH_ERROR` → `NETWORK_ERROR`), a proxy's HTML page — to a typed `ApiError`
  `{ status, code, message, details, requestId }`.
- ⏳ On 429: toast with the retry time. ⏳ `openapi-typescript` types in
  `lib/api/schema.ts` via `npm run gen:api`.
- ⏳ `lib/api/sse.ts`: streaming with `fetch` + `ReadableStream` + `TextDecoder`
  (`EventSource` cannot send an `Authorization` header), parsing `event:`/`data:` lines,
  with `AbortController` cancellation.

### 7.6 Pages

**AuthPage** ✅ — Tabs for *Password* and *Magic Link*. Sign-in, sign-up with a
six-segment strength meter and a live rule checklist (8+ chars, upper, lower, number),
"Forgot your password?" (sends a one-time email link), magic link with a 60-second resend
cooldown, error and info banners. "Email not confirmed" is rewritten into a clear message.

**DashboardPage** ✅ — Heading and a staggered, animated grid of five tool cards (GitHub,
Snippets, Notes, Timer, API Tester), each with an icon, description and, where relevant, a
count from Redux. Counts read zero until the relevant page has been visited (known gap).

**SnippetsPage** ✅ — Header with *Add Snippet*. Search (300 ms debounce, over title and
code) and tag chips derived from all loaded snippets. Two-column animated card grid: title,
language, code block, tags; hover reveals copy (with a 2-second ✓), edit, delete. Create /
edit modal with title, language, comma-separated tags and code. Delete asks via
`ConfirmDialog`. Empty state with an icon.
⏳ Phase 3: hybrid search bar with mode, filters and a match-type badge.
⏳ Phase 4: *Explain* panel (streaming markdown, level selector, Stop button) and AI tag
suggestions as accept/dismiss chips.

**NotesPage** ✅ — Two panes. Left: search and a list sorted by last update, each with a
date and a hover delete. Right: title input and a Write/Preview toggle; preview renders
GitHub-flavoured markdown through DOMPurify. Title and content auto-save 1 s after typing
stops, with a Saving…/Saved indicator. Empty state when nothing is selected.
⏳ Phase 4: *Ask your notes* panel with streaming answers and clickable `[n]` citations.

**TimerPage** ✅ — Focus (25:00) and break (5:00) modes, start/pause and reset. When a
focus period ends it records a completed session and switches to break; when a break ends
it returns to focus. Shows the completed-session count, with a reset-count action behind a
confirm dialog.
⏳ Phase 5: daily focus-minutes chart, current and best streak.

**GithubPage** ✅ — Username search (500 ms debounce) through React Query. Shows avatar,
name, bio, company, location, blog, followers, following and public repos, then the six
most recently updated repositories with description, language, stars and forks. Handles
not-found and rate-limit errors.
⏳ Phase 5: calls go through the backend; weekly insight card with *Generate now*.

**ApiTesterPage** ✅ — Method select (GET, POST, PUT, PATCH, DELETE), URL, headers as
JSON, and a body (disabled for GET and DELETE). Blocks obvious localhost/private-network
targets client-side. 10-second timeout. Shows status (coloured by class), time in ms,
headers, and a pretty-printed body that tolerates circular structures and bigints.
⏳ Phase 5: sent through the backend proxy; *Import cURL*; *Explain this error* on 4xx/5xx.

**SettingsPage** ✅ — Read-only email; change password with the same strength meter and
rules as sign-up; **API connection** card (`ApiConnectionCard`) that calls `/api/v1/me` and
shows *Connected* with the user id and email, or the error code, message and request id,
with a *Re-check* button and a hint when the API isn't running.

**AuthCallbackPage** ✅ — Reads `error`/`error_description` from the URL hash, confirms the
session, and redirects home (see R5 above).

⏳ **Everywhere:** an AI usage indicator ("12/50 AI requests left today"), and loading,
empty, error and rate-limited states on every async view.

### 7.7 Design system ✅

Dark only. Tailwind tokens in `tailwind.config.js`:

| Token | Value | Use |
|---|---|---|
| `background` | `#0f172a` | page |
| `surface` | `#111827` | cards, sidebar |
| `border` | `#1f2937` | dividers |
| `text` | `#e5e7eb` | body text |
| `accent` | `#3b82f6` | primary actions, focus rings |

Fonts: **Inter** (UI) and **JetBrains Mono** (code). Component classes in
`styles/index.css`: `.card`, `.btn-primary`, `.btn-secondary`, `.input-field`. Shared
components: `Modal` (Escape closes, body scroll lock, `aria-modal`, labelled title),
`ConfirmDialog` (async confirm with its own loading and error state), `PageLoader` /
`FullPageLoader` (`role="status"`), `AppLayout`. Merge classes with `cn()`.

**Accessibility is a requirement, not polish:** semantic HTML, keyboard reachability,
visible focus, labelled controls, `aria-live` on loading states. Keep it intact in every
new view.

---

## 8. Backend

### 8.1 Application ✅

`app/main.py` → `create_app()`:

- Configures logging (JSON in production, console otherwise) and Sentry (only when
  `SENTRY_DSN` is set; `send_default_pii=False`).
- Middleware: `RequestContextMiddleware` (request id + access log) and CORS restricted to
  `CORS_ORIGINS`, exposing `X-Request-ID` and `Retry-After`.
- Exception handlers for `AppError`, Starlette HTTP errors, request validation, and a
  catch-all that logs the traceback and returns a generic 500.
- `/docs` is served only outside production. `/openapi.json` is always available for type
  generation.
- Lifespan logs startup (environment, JWT mode, CORS origins) and disposes the engine and
  Redis pool on shutdown.

### 8.2 Configuration ✅

`core/config.py`: a `Settings` class read from the environment and `.env`, cached with
`get_settings()`. Validation fails fast at startup:

- `DATABASE_URL` must use `postgresql+asyncpg://`.
- `SUPABASE_URL` has trailing slashes stripped so the issuer string matches exactly.
- Derived: `jwt_issuer`, `jwks_url`, `cors_origin_list`, `is_production`,
  `uses_legacy_hs256` (true when `SUPABASE_JWT_SECRET` is set).
- ⏳ At startup, assert the embedding provider's dimension equals `EMBEDDING_DIM`.

Full variable reference: [environment.md](environment.md).

### 8.3 Authentication ✅

`core/security.py`. `get_current_user()` is the FastAPI dependency every protected route
uses.

1. Read `Authorization: Bearer <token>`. Missing → 401 `MISSING_TOKEN`; wrong scheme or
   empty → 401 `MALFORMED_TOKEN`.
2. Verify, in one of two modes selected by configuration:
   - **JWKS** (`SUPABASE_JWT_SECRET` unset): `PyJWKClient` against
     `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, keys cached for an hour and refetched
     on an unknown `kid`. Algorithms RS256/ES256.
   - **Legacy HS256** (`SUPABASE_JWT_SECRET` set): shared-secret verification.
3. Require `exp`, `sub`, `aud`, `iss`. Enforce `aud == "authenticated"` (so the public
   anon key, `aud: anon`, can never authenticate) and `iss == {SUPABASE_URL}/auth/v1` (so
   a token from another Supabase project is refused).
4. Return `CurrentUser(id: UUID, email: str | None)`, the id from `sub`.

Error codes: `TOKEN_EXPIRED`, `INVALID_AUDIENCE`, `INVALID_ISSUER`, `INVALID_TOKEN`. The
reason a signature failed is never echoed to the caller.

### 8.4 Errors ✅

Every failure, deliberate or not, returns one shape:

```json
{ "error": { "code": "SNIPPET_NOT_FOUND", "message": "Snippet not found.",
             "details": {}, "request_id": "b6f1…" } }
```

`AppError` subclasses: `NotFoundError` (404), `UnauthorizedError` (401),
`ValidationFailedError` (422), `RateLimitedError` and `QuotaExceededError` (429 — a
`retry_after` in `details` becomes a `Retry-After` header), `UpstreamError` (502),
`ServiceUnavailableError` (503). FastAPI's validation errors and Starlette's 404/405 are
rewritten into the same shape. Stack traces never reach the client.

### 8.5 Observability ✅

- `X-Request-ID` is read from the request or generated, stored in a `ContextVar`, returned
  on the response, added to every log line and embedded in every error body.
- One access log per request: method, path, status, `duration_ms`.
- `GET /health` — liveness; touches **nothing**, so a slow database cannot make the
  platform restart a healthy container.
- `GET /ready` — readiness; runs `SELECT 1` and a Redis `PING`, returning 503 `NOT_READY`
  with which dependency failed.

### 8.6 Database ✅

- `db/session.py`: one cached async engine (`pool_size=5`, `max_overflow=5`,
  `pool_pre_ping`), `expire_on_commit=False`, a session per request with rollback on error.
- If the URL contains `:6543` (Supabase's **transaction pooler**), asyncpg's
  prepared-statement cache is disabled automatically — otherwise statements prepared on one
  pooled backend fail on another.
- Connection strings: the API and worker use the pooled connection; **Alembic uses the
  direct or session connection**, never the transaction pooler.

### 8.7 Migrations ✅

- `alembic/env.py` restricts autogenerate to the `public` schema (`include_name`,
  `include_object`), so a migration can never propose touching Supabase's `auth`,
  `storage` or other managed schemas.
- `0001_baseline` mirrors the live schema exactly — tables, foreign keys to `auth.users`,
  grants, `update_modified_column()` triggers, RLS and all twelve owner-only policies.
- **Production is stamped, never upgraded:** `alembic stamp 0001_baseline`. The tables
  already exist and hold real data. Fresh databases run `alembic upgrade head`.
- A plain Postgres (CI, Docker) needs `scripts/auth_stub.sql` first: a minimal
  `auth.users`, `auth.uid()` and an `authenticated` role.
- Show Om the SQL of every new migration before applying it. Never drop or rewrite user
  data without asking.

### 8.8 Rate limiting and quotas ⏳ Phase 4

- Redis sliding-window limiter as a dependency, keyed by user id (IP for unauthenticated
  routes). Defaults: **120/min** general, **10/min** AI routes, **30/min** API-tester
  proxy.
- Daily AI quota per user (`AI_DAILY_QUOTA_PER_USER`, default 50), counted in `ai_usage`.
- 429 with `Retry-After` and the standard error body. Check limits and quota **before** a
  stream starts.

### 8.9 AI layer ⏳ Phases 3–4

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

Implementations: Gemini (default), at least one of Anthropic/OpenAI, and
`FakeLLMProvider`. `LLMResult` carries the parsed object plus tokens, latency and cost.
Timeouts and one retry on transient upstream errors. Prompts are **versioned templates**
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

### 8.10 Background jobs ⏳ Phase 3

ARQ worker (`workers/settings.py`, `workers/tasks.py`) sharing the API's image and
environment. Tasks: `embed_snippet`, `embed_note`, `backfill_embeddings` (batches of 32),
`weekly_insights` (cron, Mondays 06:00 IST). Jobs are enqueued **after** the transaction
commits. Transient failures retry with backoff up to 3 times; the final failure sets
`embedding_status = 'failed'`.

---

## 9. API reference

All application routes live under `/api/v1`, require a bearer token unless marked public,
and use the error format in 8.4. Lists use cursor pagination:
`?limit=20&cursor=<opaque>` → `{ "items": [...], "next_cursor": "..." | null }`.

### Infrastructure

| Method | Path | Notes | Status |
|---|---|---|---|
| GET | `/health` | public, liveness | ✅ |
| GET | `/ready` | public, Postgres + Redis | ✅ |

### Core

| Method | Path | Notes | Status |
|---|---|---|---|
| GET | `/me` | `{ id, email }` of the verified caller | ✅ |
| PATCH | `/me` | set `github_username` | ⏳ 5 |

### Snippets

| Method | Path | Notes | Status |
|---|---|---|---|
| GET | `/snippets` | filters `language`, `tag`, `favorite`; paginated | ⏳ 2 |
| POST | `/snippets` | create, then enqueue `embed_snippet` | ⏳ 2 |
| GET / PATCH / DELETE | `/snippets/{id}` | PATCH re-embeds only if the content hash changed | ⏳ 2 |
| GET | `/snippets/search?q=&mode=hybrid&language=&tag=&limit=10` | `mode` = `keyword` \| `semantic` \| `hybrid`; items carry `score` and `match_type` | ⏳ 3 |
| POST | `/snippets/{id}/ai/tags` | suggested `language`, `tags[]`, `description`; never overwrites user tags | ⏳ 4 |
| POST | `/snippets/{id}/ai/explain` | **SSE**; body `{ level: beginner \| intermediate \| expert }` | ⏳ 4 |

### Notes

| Method | Path | Notes | Status |
|---|---|---|---|
| GET / POST | `/notes` | create enqueues `embed_note` | ⏳ 2 |
| GET / PATCH / DELETE | `/notes/{id}` | edits re-chunk and re-embed only changed chunks | ⏳ 2 |
| POST | `/notes/ask` | `{ question }` → **SSE**: `sources`, then `token`s, then `done` | ⏳ 4 |

### API tester

| Method | Path | Notes | Status |
|---|---|---|---|
| POST | `/api-tester/send` | server-side proxy with SSRF protection | ⏳ 5 |
| POST | `/api-tester/parse-curl` | deterministic → `{ method, url, headers, body }` | ⏳ 5 |
| POST | `/api-tester/explain-error` | `likely_causes[]`, `suggested_fixes[]`, `confidence` | ⏳ 5 |

### Pomodoro

| Method | Path | Notes | Status |
|---|---|---|---|
| POST | `/pomodoro/sessions` | record a completed session; the server does the arithmetic | ⏳ 2 |
| GET | `/pomodoro/sessions` | paginated | ⏳ 2 |
| GET | `/pomodoro/stats?range=7d\|30d&tz=` | daily minutes, totals, current and best streak | ⏳ 5 |

### GitHub

| Method | Path | Notes | Status |
|---|---|---|---|
| GET | `/github/overview?username=` | server token, 15-min Redis cache, ETag conditional requests | ⏳ 5 |
| GET | `/github/insights?limit=4` | stored weekly insights | ⏳ 5 |
| POST | `/github/insights/generate` | on demand for the current week; counts against the AI quota | ⏳ 5 |

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

### Existing ✅ ([db/migrations/20260407000000_init_tables.sql](../db/migrations/20260407000000_init_tables.sql))

| Table | Columns |
|---|---|
| `snippets` | `id uuid pk`, `user_id uuid → auth.users`, `title text`, `code text`, `language text null`, `tags text[] default '{}'`, `created_at`, `updated_at` |
| `notes` | `id uuid pk`, `user_id uuid → auth.users`, `title text`, `content text`, `created_at`, `updated_at` |
| `user_stats` | `user_id uuid pk → auth.users`, `completed_sessions int default 0`, `updated_at` |

- RLS on all three: four owner-only policies each, `auth.uid() = user_id`.
- `update_modified_column()` maintains `updated_at` on every update.
- `handle_new_user()` (`SECURITY DEFINER`) inserts a `user_stats` row after a user is
  created in `auth.users`.
- Only primary-key indexes exist — no index on `user_id` yet.

### Planned ⏳

Adapt names to the live schema; show the SQL before applying.

**Snippets (Phase 3)** — add `description text` (the embedding text needs it) and decide
on `favorite boolean`; `content_hash text`; `embedding vector(384)`;
`embedding_status text not null default 'pending'` in (`pending`, `ready`, `failed`);
`embedded_at timestamptz`; `ai_tags text[]`, `ai_description text`, `ai_language text`;
`search_tsv tsvector` **generated always … stored**, weighted title (A), description (B),
tags (B), code (C, `simple` config). Indexes: HNSW on `embedding` (`vector_cosine_ops`),
GIN on `search_tsv`, B-tree on `user_id`.

**`note_chunks` (Phase 4)** — `id`, `note_id → notes on delete cascade`, `user_id`,
`chunk_index`, `heading`, `content`, `content_hash`, `token_count`, `embedding vector(384)`,
generated `search_tsv`, `created_at`, `unique(note_id, chunk_index)`; HNSW, GIN and
`user_id` indexes; RLS owner-only.

**`ai_usage` (Phase 4)** — `id`, `user_id`, `feature` (`explain_code` | `auto_tag` |
`ask_notes` | `explain_http_error` | `github_insights`), `provider`, `model`,
`input_tokens`, `output_tokens`, `cost_usd numeric(10,6)`, `latency_ms`, `status`
(`success` | `error` | `quota_exceeded`), `error_code`, `created_at`; index
`(user_id, created_at)`.

**`pomodoro_sessions` (Phase 2/5)** — per-session history, replacing the single counter so
daily minutes and streaks can be computed in SQL.

**`github_insights` (Phase 5)** — `id`, `user_id`, `github_username`, `week_start date`,
`stats jsonb`, `summary jsonb`, `created_at`, `unique(user_id, week_start)`.

**`profiles` (Phase 5)** — holds `github_username`; none exists today.

**Hardening (first Phase 2 migration)** — `SET search_path = public, pg_temp` on
`handle_new_user()`; `user_id` indexes; revoke any `anon` grant; decide `ON DELETE`
behaviour so deleting a user doesn't strand their snippets and notes.

---

## 11. Features in depth

### 11.1 Embedding pipeline ⏳ Phase 3

- Snippet embedding text: `title + description + user tags + language + code`, truncated
  to the model's 512-token limit.
- **Idempotency:** hash the embedding text; if the hash is unchanged and status is
  `ready`, skip. This is what makes a 1-second notes autosave harmless.
- Always in the worker, never inside the request. `scripts/backfill_embeddings.py` for
  existing rows.

### 11.2 Hybrid search ⏳ Phase 3

One SQL query with CTEs, always scoped to `user_id` and the filters:

1. **Keyword:** `websearch_to_tsquery('english', :q)` against `search_tsv`, ranked by
   `ts_rank_cd`, top 50.
2. **Semantic:** embed the query (cached in Redis by query hash, 1 h), order by
   `embedding <=> :qvec`, top 50, only `embedding_status = 'ready'`.
3. **Fusion:** `score = Σ 1 / (60 + rank)` across branches; return the top `limit`.

`match_type` is `keyword`, `semantic` or `both`. `mode=keyword|semantic` return one branch,
which the evaluation needs. Comment in the code why RRF beats adding raw scores.

### 11.3 Explain this code ⏳ Phase 4

Redact → versioned prompt → stream tokens as SSE. Quota and rate limit checked first;
`ai_usage` recorded on completion and on error; upstream cancelled on disconnect.

### 11.4 Auto-tagging ⏳ Phase 4

```python
class SnippetTagSuggestion(BaseModel):
    language: str        # normalised, lowercase
    tags: list[str]      # 3-5 lowercase kebab-case
    description: str     # one sentence, max 140 chars
```

Validate with Pydantic; on failure retry **once** with the validation error in the prompt,
then return a clean error. Normalise (lowercase, dedupe, max 5). The user accepts
suggestions explicitly; user tags are never overwritten.

### 11.5 Ask your notes ⏳ Phase 4

- **Chunking:** split by markdown heading, then ~300-token windows with ~50 overlap;
  keep the nearest heading for citations.
- **Re-embedding:** compare chunk hashes; embed new or changed chunks only, delete removed.
- **Retrieval:** hybrid search over `note_chunks`, top 6.
- **Guardrail:** if the best semantic similarity is under a configurable threshold, answer
  "I couldn't find this in your notes" **without calling the LLM**.
- **Generation:** numbered sources; the model must cite `[n]` and answer only from them.

### 11.6 API tester proxy ⏳ Phase 5

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

### 11.7 Pomodoro stats ⏳ Phase 5

In SQL (`date_trunc`, window functions) in the user's timezone (`tz`, default
`Asia/Kolkata`). Unit-test streaks across gaps, multiple sessions a day, and midnight in
other timezones.

### 11.8 GitHub overview and weekly insights ⏳ Phase 5

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

| Control | Where | Status |
|---|---|---|
| JWT verification: signature, `exp`, `aud`, `iss` | `core/security.py` | ✅ |
| Identity from the token's `sub`, never from the request body | every route | ✅ / ⏳ enforced from Phase 2 |
| Every query filtered by `user_id`; cross-user → 404 | repositories | ⏳ 2 |
| IDOR tests for every resource | tests | ⏳ 2 |
| RLS kept on | Postgres | ✅ |
| CORS restricted to `CORS_ORIGINS` | `main.py` | ✅ |
| No stack traces or internal messages to clients | error handlers | ✅ |
| Non-root container | Dockerfile | ✅ |
| Secret redaction before any LLM call | `redaction.py` | ⏳ 4 |
| Rate limits and daily AI quota | limiter | ⏳ 4 |
| SSRF protection on the proxy | `api_tester.py` | ⏳ 5 |
| Request body size limits | middleware | ⏳ |
| Bound parameters only — never string-formatted SQL | everywhere | ✅ |
| `pip-audit` in CI | CI | ✅ (non-blocking) |

**Secrets:** the anon key is public by design and ships in the bundle; RLS protects rows.
Nothing secret may ever carry a `VITE_` prefix — it would be inlined into the JavaScript.
`SUPABASE_SERVICE_ROLE_KEY` is **never** used: the backend reaches Postgres through
SQLAlchemy, not supabase-js.

---

## 13. Testing and evaluation

### Current ✅

- **Backend — 31 tests.** Config validation; every way a token can be wrong (missing,
  malformed, expired, wrong audience, wrong issuer, unknown key, each required claim
  dropped, non-UUID subject, `alg=none` forgery); HS256 mode; error shape and request ids;
  `/health`, `/ready` against real Postgres and Redis, and `/ready` returning 503.
- **Frontend — 10 tests.** `toApiError` mapping; the base query's token attachment,
  refresh-and-retry, sign-out on failed refresh, a single shared refresh under concurrent
  401s, and no refresh on non-401 errors.
- Tests **never contact Supabase**: a key pair is generated per session and the JWKS lookup
  is pointed at it, so the real verification path runs against tokens the tests control.

### Required as phases land ⏳

- IDOR: cross-user access to every resource type returns 404.
- CRUD for snippets, notes, sessions.
- Search ranking with deterministic fake embeddings (keyword-only, semantic-only, both).
- Embedding idempotency; rate limiter and quota → 429 with `Retry-After`; every redaction
  pattern; SSRF cases (private IPs, localhost, metadata IP, IPv6 loopback, redirect to a
  private IP, non-http scheme); cURL parser cases; SSE event format and the error event;
  pomodoro streak edge cases; the SSE parser with chunks split mid-line; search component
  states.
- **≥ 80% coverage** on `services/` and `repositories/`.
- **No test may call a paid API.** Fakes are the default.

### Search evaluation ⏳ Phase 6

`evals/search/`: ~60 realistic snippets (JS/TS/Python/SQL/CSS), 30 queries in
`queries.yaml` with expected ids — including ones keywords fail on ("stop a function from
firing too often" → debounce). Report **Recall@5**, **MRR@10** and p50/p95 latency for
keyword, semantic and hybrid; write timestamped JSON and a Markdown table for the README.

---

## 14. Running, building, deploying

### Local

```bash
docker compose up -d postgres redis                                  # Postgres on 5434
cd backend && cp .env.example .env                                   # then set SUPABASE_URL
uv run alembic upgrade head && uv run uvicorn app.main:app --reload  # API on :8000
cd frontend && npm install && npm run dev                            # app on :5173
```

`cp .env.example .env` **overwrites** an existing `.env` — copy only once.
On non-Supabase Postgres, apply `backend/scripts/auth_stub.sql` before migrating.
The API and the frontend each need their own terminal.

### Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd frontend && npm run lint && npm run check && npm test && npm run build
```

### CI ✅

GitHub Actions on every push to `main` and every PR. **Backend:** uv sync, ruff, ruff
format, mypy, auth stub, `alembic upgrade head`, pytest with coverage against Postgres and
Redis service containers, `pip-audit`. **Frontend:** `npm ci`, lint, typecheck, Vitest,
build with placeholder env values. CI holds no real credentials.

### Deployment

- **Frontend** ✅ — Vercel, Root Directory `frontend`. Env vars are inlined at **build**
  time: after changing one, redeploy with *Use existing Build Cache* **off**. Supabase
  values are accepted as `VITE_SUPABASE_*` or plain `SUPABASE_*`.
- **Backend** ⏳ Phase 6 — API and worker on Render from the same image, Upstash Redis,
  `CORS_ORIGINS` set to the real Vercel origin, `alembic stamp` then `upgrade` on
  production, embeddings backfilled.

### Environment variables

| Frontend | Backend |
|---|---|
| `VITE_SUPABASE_URL` | `APP_ENV`, `LOG_LEVEL` |
| `VITE_SUPABASE_ANON_KEY` | `DATABASE_URL`, `REDIS_URL` |
| `VITE_API_URL` | `SUPABASE_URL`, `SUPABASE_JWT_SECRET` (HS256 only) |
| | `CORS_ORIGINS` |
| | `LLM_PROVIDER`, `LLM_MODEL`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` |
| | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` |
| | `GITHUB_TOKEN`, `AI_DAILY_QUOTA_PER_USER`, `SENTRY_DSN` |

Where each comes from and which are secret: [environment.md](environment.md).

---

## 15. Phases and acceptance criteria

| Phase | Done when |
|---|---|
| **0 Audit** ✅ | Every Supabase call site, the schema, auth mode, Redux shape, risks and the migration order are documented and approved |
| **1 Foundation** ✅ built | Signed in locally, **Settings → API connection shows your Supabase user id**; CI green |
| **2 CRUD** | Snippets → notes → pomodoro work through the API exactly as before; direct Supabase data calls for them are gone; IDOR tests pass |
| **3 Search** | An intent-style query finds a snippet keyword search misses; existing snippets are backfilled |
| **4 AI** | Explain, auto-tag and Ask your notes work in the UI; `ai_usage` rows record cost; quota and limits return 429 |
| **5 Proxy, stats, GitHub** | The tester reaches APIs that failed on CORS; SSRF tests pass; insights generate and display |
| **6 Eval & deploy** | Evaluation table exists; production API and worker run; README matches what shipped |

**Phase 2 guidance from the audit:**

- Migrate with a large page size first and let Phase 3's search take over filtering —
  tag chips, in-memory search and dashboard counts all assume the whole collection is
  loaded, and cursor pagination would break all three at once.
- `activeNoteId` is UI state and stays in Redux; the collections move to RTK Query.
- The timer should post "a session finished" and let the server do the arithmetic, not
  upsert a browser-computed total.
- Delete `lib/supabase/session.ts` at the end — nothing should need the browser to supply
  a user id.

---

## 16. Non-negotiables

- Do not remove or weaken RLS, or change Supabase Auth flows.
- Do not let Alembic touch `auth`, `storage` or other Supabase-managed schemas.
- Do not run embeddings or LLM calls inside a request, except the two streaming endpoints.
- Do not send unredacted user content to an LLM.
- Do not format SQL with strings.
- Do not trust a `user_id` from the request body.
- Do not put a secret in a `VITE_` variable or in git.
- Do not add a dependency without saying why.
- Do not drop or rewrite user data without asking; show migration SQL first.
- Do not move to the next phase without Om's confirmation.

---

## 17. Open questions

| Question | Blocks |
|---|---|
| Recreate the Supabase project (the old one returns NXDOMAIN)? | Phase 1 sign-off, production sign-in |
| JWKS or legacy HS256 on the (new) project? | Phase 1 sign-off |
| Does the live schema match the migration? (Moot if the project is recreated from it.) | Phase 2 migrations |
| Which connection strings for API, worker and Alembic? | Phase 6 deploy |
| Are `snippets.description` and `favorite` in scope? | Phase 3 |
| Keep `user_stats.completed_sessions` as a baseline once session rows exist? | Phase 5 |
| Fix "Forgot password" to use `resetPasswordForEmail`, or reword it? | anytime |
| What is the real production Vercel origin for `CORS_ORIGINS`? | Phase 6 |
