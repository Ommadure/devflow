# ADR 0002: Every query is scoped by `user_id` in the repository layer

- **Status:** Accepted
- **Date:** 2026-09-26
- **Replaces:** the original "API authorizes by `user_id`; Supabase RLS stays on"

## Context
Every DevFlow resource belongs to exactly one user. The original design kept Postgres
Row-Level Security as defence in depth, but those policies relied on Supabase's
`auth.uid()`. On plain Postgres (Neon) the API connects as a single database role, so RLS
would need a per-request `SET` of the user id — extra machinery that is easy to get
subtly wrong with connection pooling.

## Decision
- The user id comes **only** from the verified access token (`sub`), never from a request
  body, query string or path.
- **Every repository method takes `user_id` and filters by it** — reads, updates and
  deletes alike (`WHERE id = :id AND user_id = :user_id`).
- A row owned by someone else is indistinguishable from a missing row: **404, not 403**.
  A 403 would confirm the id exists.
- Every resource gets an **IDOR test**: user B tries to read, update and delete user A's
  row and gets 404, and A's row is unchanged.

## Consequences
- One place to audit (repositories) and one kind of test that proves it.
- A forgotten filter is a data leak with no second line of defence — which is why the IDOR
  tests are required for every resource, not optional.

## Alternatives considered
- **RLS with `SET LOCAL app.user_id` per transaction**: real defence in depth, but it must
  run inside every transaction, interacts with PgBouncer's transaction pooling, and is
  hard to explain briefly. A good follow-up if DevFlow ever has multiple services.
- **Authorization checks in services only**: easy to forget on one code path; filtering in
  the query can't be skipped.
