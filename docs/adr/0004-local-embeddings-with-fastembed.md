# ADR 0004: FastEmbed `bge-small-en-v1.5` for embeddings

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
Semantic search and "ask your notes" need text embeddings for every snippet and note
chunk, re-computed on edits. A hosted embedding API costs money per call, adds a network
dependency to every save, and sends user content to a third party.

## Decision
- **FastEmbed** running `BAAI/bge-small-en-v1.5` locally in the worker (and in the API,
  for query embeddings only).
- 384 dimensions, stored in `vector(384)` columns; `EMBEDDING_DIM` is checked against the
  model at startup.
- The model is downloaded at **Docker build time**, so containers start without network.
- Inference runs in `asyncio.to_thread` so it does not block the event loop.
- An `EmbeddingProvider` protocol hides the implementation; tests use deterministic fake
  vectors.

## Consequences
- $0 per embedding and no user content leaves the server for search.
- FastEmbed uses ONNX Runtime, so the image stays free of PyTorch (hundreds of MB smaller).
- Quality is below the largest hosted models; the Phase 7 evaluation measures whether it
  is good enough.
- The model costs memory in each process that loads it — a constraint on the free VM.

## Alternatives considered
- **Hosted embeddings (Gemini, OpenAI)**: better quality, but per-call cost, rate limits
  and a third party seeing every snippet.
- **sentence-transformers**: the same models, but pulls in PyTorch.
