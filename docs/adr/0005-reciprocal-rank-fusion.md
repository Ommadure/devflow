# ADR 0005: Reciprocal Rank Fusion for hybrid search

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
Keyword search (Postgres full-text) is precise for exact names ("useDebounce") but misses
intent ("stop a function from firing too often"). Vector search finds intent but can miss
exact identifiers. Combining them means merging two ranked lists whose scores are on
different, incomparable scales (`ts_rank_cd` vs cosine distance).

## Decision
- Run both branches in one SQL query (CTEs), each returning its top 50 for the user.
- Fuse with **Reciprocal Rank Fusion**: `score = Σ 1 / (60 + rank)` over the branches a
  result appears in. `k = 60` is the value from the original RRF paper.
- Report `match_type` (`keyword`, `semantic`, `both`); `mode=keyword|semantic` return a
  single branch so the evaluation can compare all three.

## Consequences
- No score normalisation or weight tuning; the formula is easy to explain and test.
- Only ranks matter, so a very strong match counts the same as a narrow first place.
- Two index scans per query; fine at a personal-dashboard scale.

## Alternatives considered
- **Weighted sum of normalised scores**: needs per-dataset tuning and min-max
  normalisation that shifts with every query.
- **Vector search only**: fails on exact identifiers and short queries.
- **A re-ranking model**: better, but another model to host and a latency cost.
