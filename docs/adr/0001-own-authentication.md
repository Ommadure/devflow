# ADR 0001: The API owns authentication

- **Status:** Accepted
- **Date:** 2026-09-26
- **Replaces:** the original "keep Supabase Auth; the API verifies its JWTs"

## Context
The original DevFlow signed users in with Supabase Auth, and the backend only verified
Supabase's JWTs. That Supabase project no longer exists, and the rebuild starts with no
users. DevFlow is a resume project: Om has to be able to explain every link of the auth
chain, and "a hosted service does it" is the weakest possible answer to the most common
backend interview topic.

## Decision
- **Email + password only.** No magic links, no password reset by email, no email
  verification — each needs an email provider and a sending domain, and none teaches
  anything the core flow doesn't.
- **Passwords:** argon2id (`argon2-cffi`, RFC 9106 default parameters), rehashed on login
  when the parameters change. Unknown emails still pay for one dummy verification so
  timing doesn't reveal which accounts exist.
- **Access token:** a 15-minute HS256 JWT (`sub`, `iat`, `exp`, `iss`, `aud`), returned
  in the response body and kept **only in frontend memory**.
- **Refresh token:** 32 random bytes in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie
  scoped to `/api/v1/auth`, valid 30 days. Stored as a SHA-256 hash. **Rotated** on every
  use; presenting a revoked token revokes its whole family (reuse detection).
- **Same origin:** the browser reaches the API through `/api` on its own origin (Vite
  proxy locally, Vercel rewrite in production), so the cookie is first-party.
- **CSRF:** only `/auth/refresh` and `/auth/logout` read the cookie; `SameSite=Lax` plus an
  `Origin` allow-list protects them. Everything else uses a bearer header.

## Consequences
- Om can explain hashing, token lifetimes, rotation, XSS vs CSRF trade-offs end to end.
- DevFlow now stores credentials, so it carries the responsibility: rate-limited login,
  no plaintext secrets, nothing sensitive in logs.
- Access tokens are stateless: after logout or a password change, an issued access token
  still works until it expires (≤ 15 min). Short lifetimes make that acceptable; a
  deny-list would make every request hit Redis.
- No password reset: a user who forgets their password cannot recover the account. That
  is acceptable for a portfolio app and is stated in the UI.

## Alternatives considered
- **Recreate a Supabase project**: fastest, but auth becomes someone else's black box and
  data would split across two providers.
- **Access token in `localStorage`**: simpler, but any XSS can read and exfiltrate it.
- **Session id cookie + server-side sessions only**: simpler still, but every request hits
  the session store and there's no JWT to discuss — JWT + refresh is what most job
  descriptions ask about.
- **RS256 / JWKS**: needed only when *other* services verify the tokens. One API issues
  and verifies them, so a shared secret is enough; the verifier can move to asymmetric
  keys later without touching clients.
- **OAuth sign-in (GitHub/Google)**: ReviewPilot already demonstrates OAuth; password auth
  covers different ground.
