# Architecture Decision Records

One short file per decision that shapes DevFlow: what we chose, why, what it costs, and
what we rejected. An ADR is never edited to change its decision — a new ADR supersedes it.

| # | Decision | Status |
|---|---|---|
| [0001](0001-own-authentication.md) | The API owns authentication: email + password, access JWT, rotating refresh cookie | Accepted |
| [0002](0002-user-scoping-in-the-api.md) | Every query is scoped by `user_id` in the repository layer | Accepted |
| [0003](0003-taskiq-for-background-jobs.md) | Taskiq for background jobs | Accepted |
| [0004](0004-local-embeddings-with-fastembed.md) | FastEmbed `bge-small-en-v1.5` for embeddings | Accepted |
| [0005](0005-reciprocal-rank-fusion.md) | Reciprocal Rank Fusion for hybrid search | Accepted |
| [0006](0006-server-side-api-tester.md) | The API tester is proxied server-side, with SSRF protection | Accepted |
| [0007](0007-monorepo-by-deployable.md) | One repository, split by deployable | Accepted |
| [0008](0008-hosting-neon-oracle-vercel.md) | Neon + an Oracle Always Free VM + Vercel | Accepted; VM sharing superseded by 0009 |
| [0009](0009-own-a1-vm-and-client-ip.md) | DevFlow gets its own A1 VM; the API trusts the forwarded client IP | Accepted |

**History.** The first version of DevFlow used Supabase for auth and data, and ARQ for
jobs. That code was deleted on 2026-09-26; these records were rewritten for the rebuild,
and each one notes what it replaced.
