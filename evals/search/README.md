# Search evaluation

Does snippet search find what a person meant? 60 snippets saved the way people actually
save them (terse titles, often no description) and 30 queries with the snippets a person
would accept, scored for each search mode.

| File | What |
|---|---|
| `snippets.yaml` | the corpus: 16 Python, 15 JavaScript, 12 SQL, 10 CSS, 7 TypeScript |
| `queries.yaml` | 30 queries — 10 `keyword` (a name that appears in the snippet), 16 `intent` (the goal in other words), 4 `mixed` — plus 6 questions nothing answers |
| `run.py` | the runner (logic in `backend/app/evals/search.py`, type-checked and tested) |
| `results/` | one JSON + Markdown pair per recorded run |

```bash
cd backend
uv run python ../evals/search/run.py                     # real model; writes results/
uv run python ../evals/search/run.py --max-distance 0.45 # try another cut-off
uv run python ../evals/search/run.py --provider fake --no-write   # plumbing only
```

It uses the database in `backend/.env`, stores the corpus for a throwaway user (with the
same embedding text and status the worker would write), runs every query through the
same `hybrid_search` the API calls, and deletes that user at the end. Nothing else in the
database is read or changed.

**Metrics.** *Recall@5*: the share of acceptable snippets in the top 5 (the first
screen). *MRR@10*: the mean of 1 / position of the first acceptable snippet (0 if none in
the top 10) — how high the answer sits. *No-answer questions with results*: how often
search shows something when nothing is right. *Latency*: embedding the query as on a
cache miss, plus the SQL query.

## Results (2026-09-27, `bge-small-en-v1.5`, cut-off 0.40)

| Mode | Recall@5 | MRR@10 | p50 | p95 | No-answer questions with results |
|---|---|---|---|---|---|
| keyword | 0.33 | 0.33 | 10 ms | 30 ms | 0/6 |
| semantic | 0.82 | 0.76 | 28 ms | 44 ms | 3/6 |
| **hybrid** | **0.85** | **0.79** | 32 ms | 52 ms | 3/6 |

| Recall@5 by phrasing | keyword | intent | mixed |
|---|---|---|---|
| keyword | 1.00 | 0.00 | 0.00 |
| semantic | 0.90 | 0.81 | 0.62 |
| hybrid | 1.00 | 0.81 | 0.62 |

Full report: [`results/20260927-182643_baai-bge-small-en-v1-5.md`](results/20260927-182643_baai-bge-small-en-v1-5.md).

## What it shows, and what was decided

**Hybrid is the right default.** Keyword search is perfect when you type a name and
useless when you describe a goal (0 of 16 intent queries). Semantic search finds intent
but slips on exact names (0.90). Fusing them keeps both strengths — no weighting to tune,
because RRF works on ranks (ADR 0005).

**The semantic cut-off stays at cosine distance 0.40, now for a measured reason.**

| Cut-off | Hybrid Recall@5 | No-answer questions with results |
|---|---|---|
| 0.35 | 0.62 | 0/6 |
| **0.40** | **0.85** | 3/6 |
| 0.45 | 0.92 | 5/6 |

Right answers sit at distance 0.19–0.51 (median 0.33); the nearest snippet to a question
with no answer sits at 0.37–0.47. The two ranges overlap, so no single number gives both
full recall and silence on nonsense. 0.40 is the knee: from 0.35 it buys +0.23 recall for
3 weak results on no-answer questions; going to 0.45 buys only +0.07 more for 2 more. In a
personal snippet library, a weak extra result (marked "semantic") costs less than a
missing right one. "Ask your notes" uses the same line (similarity 0.60) for its
no-LLM guardrail.

**The misses** are snippets whose saved text says little: `sleep` for "wait a few seconds
before continuing", `timed()` for "how long did this block of code take", a Python
`Semaphore` for "limit how many downloads run at once". Options, not yet taken: embed the
one-sentence description auto-tagging already generates; a larger model (bge-base, 768
dimensions — a migration and a re-embed); a reranker over the top 20.

**It led to a real bug fix.** Checking whether these numbers would hold with many users
showed they wouldn't: pgvector filters `user_id` *after* the HNSW index scan, so once
other users' vectors crowd the neighbourhood, a user's own matches drop out — in a
reproduction, all of them. Fixed with pgvector 0.8's iterative scans
(`app/repositories/_vector.py`, regression test `tests/integration/test_vector_scan.py`).
This corpus alone is too small to show it: at 60 rows Postgres doesn't use the index.

## Caveats
- 30 queries is small: one query moves Recall@5 by about 0.03. Treat differences under
  ~0.07 as noise.
- The queries were written by the same person as the corpus. Intent queries were checked
  to share no meaningful word with their target, but a stranger's phrasing would differ.
- Latency was measured in-process on a laptop that was busy with other work (load ~10 on
  8 cores); compare modes against each other, not against a production SLO. Repeated
  queries skip the embedding entirely (Redis cache, 1 h).
