"""Search evaluation (spec §13): does each search mode find the snippet a person meant?

Loads evals/search/{snippets,queries}.yaml, stores the snippets for a throwaway user with
real embeddings, runs every query through the same `hybrid_search` the API uses, and
deletes that user (and, by cascade, its snippets) at the end — also when something fails.

    cd backend && uv run python ../evals/search/run.py      # see evals/search/README.md
"""

import argparse
import asyncio
import json
import re
import statistics
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.evals.metrics import mean, percentile, recall_at, reciprocal_rank
from app.models import Snippet, User
from app.repositories.search import Filters, Mode, hybrid_search
from app.services.ai.embedding_text import content_hash, embedding_text
from app.services.ai.embeddings import EmbeddingProvider, Vector
from app.services.search import DEFAULT_MAX_DISTANCE

MODES: tuple[Mode, ...] = ("keyword", "semantic", "hybrid")
KINDS = ("keyword", "intent", "mixed")
Kind = Literal["keyword", "intent", "mixed"]
RECALL_K, MRR_K = 5, 10
CUTOFFS = (0.30, 0.35, 0.40, 0.45, 0.50)
Sessions = async_sessionmaker[AsyncSession]


class EvalSnippet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    code: str
    language: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()


class EvalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    q: str
    kind: Kind
    relevant: Annotated[tuple[str, ...], Field(min_length=1)]


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snippets: list[EvalSnippet]
    queries: list[EvalQuery]
    no_answer: list[str] = []

    @model_validator(mode="after")
    def _references_exist(self) -> "Dataset":
        ids = [snippet.id for snippet in self.snippets]
        if duplicates := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"duplicate snippet ids: {duplicates}")
        if unknown := sorted({r for q in self.queries for r in q.relevant} - set(ids)):
            raise ValueError(f"queries refer to unknown snippets: {unknown}")
        return self


def load_dataset(directory: Path) -> Dataset:
    queries = yaml.safe_load((directory / "queries.yaml").read_text())
    return Dataset(
        snippets=yaml.safe_load((directory / "snippets.yaml").read_text()),
        queries=queries["queries"],
        no_answer=queries.get("no_answer") or [],
    )


# ---- running ---------------------------------------------------------------------------


async def run(
    sessions: Sessions,
    provider: EmbeddingProvider,
    dataset: Dataset,
    *,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    cutoffs: Sequence[float] = CUTOFFS,
    repeats: int = 3,
) -> dict[str, Any]:
    user_id = uuid.uuid4()
    async with sessions() as session:
        # "!" is not an argon2 hash, so nobody can ever sign in as this user.
        email = f"eval-{user_id.hex}@example.invalid"
        session.add(User(id=user_id, email=email, password_hash="!"))  # noqa: S106
        await session.commit()
    try:
        async with sessions() as session:
            names = await _insert(session, provider, user_id, dataset.snippets)
            await session.commit()
        async with sessions() as session:
            evaluation = _Evaluation(session, provider, user_id, names, dataset)
            return await evaluation.report(max_distance, cutoffs, repeats)
    finally:
        async with sessions() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def _insert(
    session: AsyncSession,
    provider: EmbeddingProvider,
    user_id: uuid.UUID,
    snippets: Sequence[EvalSnippet],
) -> dict[uuid.UUID, str]:
    """Stored exactly as the worker would: the same embedding text, hash and status."""
    rows = [
        Snippet(
            user_id=user_id,
            title=s.title,
            description=s.description,
            code=s.code,
            language=s.language,
            tags=list(s.tags),
        )
        for s in snippets
    ]
    texts = [embedding_text(row) for row in rows]
    vectors: list[Vector] = []
    for start in range(0, len(texts), 32):
        vectors += await provider.embed_documents(texts[start : start + 32])
    now = datetime.now(UTC)
    for row, text, vector in zip(rows, texts, vectors, strict=True):
        row.embedding = vector
        row.content_hash = content_hash(text, provider.model_name)
        row.embedding_status = "ready"
        row.embedded_at = now
    session.add_all(rows)
    await session.flush()
    return {row.id: s.id for row, s in zip(rows, snippets, strict=True)}


class _Evaluation:
    def __init__(
        self,
        session: AsyncSession,
        provider: EmbeddingProvider,
        user_id: uuid.UUID,
        names: dict[uuid.UUID, str],
        dataset: Dataset,
    ) -> None:
        self._session = session
        self._provider = provider
        self._user_id = user_id
        self._names = names
        self._dataset = dataset
        self._vectors: dict[str, Vector] = {}

    async def report(
        self, max_distance: float, cutoffs: Sequence[float], repeats: int
    ) -> dict[str, Any]:
        await self._provider.embed_query("warm up")  # loads the model outside any timing
        for q in [query.q for query in self._dataset.queries] + self._dataset.no_answer:
            self._vectors[q] = await self._provider.embed_query(q)
        return {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": self._provider.model_name,
            "max_distance": max_distance,
            "snippets": len(self._dataset.snippets),
            "queries": len(self._dataset.queries),
            "no_answer": len(self._dataset.no_answer),
            "repeats": repeats,
            "modes": {mode: await self._mode(mode, max_distance, repeats) for mode in MODES},
            "cutoff_sweep": [await self._sweep_row(cutoff) for cutoff in cutoffs],
            "distances": await self._distances(),
        }

    async def _search(
        self, q: str, mode: Mode, max_distance: float, *, cached: bool
    ) -> tuple[list[str], float]:
        """Latency = embedding the query (as on a Redis cache miss) + the SQL query."""
        start = time.perf_counter()
        vector = None
        if mode != "keyword":
            vector = self._vectors[q] if cached else await self._provider.embed_query(q)
        hits = await hybrid_search(
            self._session,
            self._user_id,
            q=q,
            vector=vector,
            mode=mode,
            filters=Filters(),
            max_distance=max_distance,
            limit=MRR_K,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        return [self._names[hit.snippet.id] for hit in hits], elapsed_ms

    async def _mode(self, mode: Mode, max_distance: float, repeats: int) -> dict[str, Any]:
        latencies: list[float] = []
        results: list[dict[str, Any]] = []
        for query in self._dataset.queries:
            for _ in range(repeats):
                ranked, elapsed_ms = await self._search(query.q, mode, max_distance, cached=False)
                latencies.append(elapsed_ms)
            results.append(
                {
                    "q": query.q,
                    "kind": query.kind,
                    "relevant": list(query.relevant),
                    "ranked": ranked,
                    "recall_at_5": recall_at(ranked, query.relevant, RECALL_K),
                    "rr_at_10": reciprocal_rank(ranked, query.relevant, MRR_K),
                }
            )
        return {
            **_scores(results),
            "latency_ms": {
                "p50": round(percentile(latencies, 50), 1),
                "p95": round(percentile(latencies, 95), 1),
            },
            "by_kind": {
                kind: _scores([r for r in results if r["kind"] == kind])
                for kind in KINDS
                if any(r["kind"] == kind for r in results)
            },
            "no_answer_with_results": await self._noise(mode, max_distance),
            "results": results,
        }

    async def _noise(self, mode: Mode, max_distance: float) -> int:
        """How many questions the corpus can't answer still got results."""
        count = 0
        for q in self._dataset.no_answer:
            ranked, _ = await self._search(q, mode, max_distance, cached=True)
            count += bool(ranked)
        return count

    async def _sweep_row(self, cutoff: float) -> dict[str, Any]:
        row: dict[str, Any] = {"max_distance": cutoff}
        for mode in ("semantic", "hybrid"):
            results = []
            for query in self._dataset.queries:
                ranked, _ = await self._search(query.q, mode, cutoff, cached=True)
                results.append(
                    {
                        "recall_at_5": recall_at(ranked, query.relevant, RECALL_K),
                        "rr_at_10": reciprocal_rank(ranked, query.relevant, MRR_K),
                    }
                )
            row[mode] = {
                **_scores(results),
                "no_answer_with_results": await self._noise(mode, cutoff),
            }
        return row

    async def _distances(self) -> dict[str, Any]:
        """Where the cut-off has to sit: how far the right answer is, against how close the
        nearest snippet is for a question with no answer."""

        async def all_distances(q: str) -> dict[str, float]:
            distance = Snippet.embedding.cosine_distance(self._vectors[q])
            rows = await self._session.execute(
                select(Snippet.id, distance).where(Snippet.user_id == self._user_id)
            )
            return {self._names[snippet_id]: float(d) for snippet_id, d in rows}

        best_relevant = []
        for query in self._dataset.queries:
            distances = await all_distances(query.q)
            best_relevant.append(round(min(distances[r] for r in query.relevant), 3))
        nearest_no_answer = [
            round(min((await all_distances(q)).values()), 3) for q in self._dataset.no_answer
        ]
        return {
            "best_relevant": _spread(best_relevant),
            "nearest_for_no_answer": _spread(nearest_no_answer),
        }


def _scores(results: Sequence[dict[str, Any]]) -> dict[str, float]:
    return {
        "recall_at_5": round(mean([r["recall_at_5"] for r in results]), 3),
        "mrr_at_10": round(mean([r["rr_at_10"] for r in results]), 3),
    }


def _spread(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"values": []}
    return {
        "min": min(values),
        "median": round(statistics.median(values), 3),
        "max": max(values),
        "values": list(values),
    }


# ---- reporting -------------------------------------------------------------------------


def render_markdown(report: dict[str, Any]) -> str:
    modes, no_answer = report["modes"], report["no_answer"]
    lines = [
        f"### Search evaluation, {report['timestamp']}",
        "",
        f"{report['snippets']} snippets, {report['queries']} queries and {no_answer} questions "
        f"with no answer; model `{report['model']}`; semantic cut-off: cosine distance "
        f"≤ {report['max_distance']}. Latency is embedding the query (a cache miss) plus the "
        f"SQL query, {report['repeats']} runs per query, measured in-process.",
        "",
        "| Mode | Recall@5 | MRR@10 | p50 | p95 | No-answer questions with results |",
        "|---|---|---|---|---|---|",
    ]
    for mode, m in modes.items():
        lines.append(
            f"| {mode} | {m['recall_at_5']:.2f} | {m['mrr_at_10']:.2f} | "
            f"{m['latency_ms']['p50']:.0f} ms | {m['latency_ms']['p95']:.0f} ms | "
            f"{m['no_answer_with_results']}/{no_answer} |"
        )
    kinds = [k for k in KINDS if k in modes["hybrid"]["by_kind"]]
    lines += ["", "Recall@5 by how the query is phrased:", ""]
    lines += ["| Mode | " + " | ".join(kinds) + " |", "|---|" + "---|" * len(kinds)]
    for mode, m in modes.items():
        cells = [f"{m['by_kind'][k]['recall_at_5']:.2f}" for k in kinds]
        lines.append(f"| {mode} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Semantic cut-off sweep (cosine distance ≤ x):",
        "",
        "| Cut-off | Semantic R@5 | Semantic MRR | Hybrid R@5 | Hybrid MRR "
        "| No-answer with results |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["cutoff_sweep"]:
        s, h = row["semantic"], row["hybrid"]
        lines.append(
            f"| {row['max_distance']:.2f} | {s['recall_at_5']:.2f} | {s['mrr_at_10']:.2f} | "
            f"{h['recall_at_5']:.2f} | {h['mrr_at_10']:.2f} | "
            f"{h['no_answer_with_results']}/{no_answer} |"
        )
    d = report["distances"]
    if "min" in d["nearest_for_no_answer"]:
        best, noise = d["best_relevant"], d["nearest_for_no_answer"]
        lines += [
            "",
            f"Distance to the best right answer: min {best['min']}, median {best['median']}, "
            f"max {best['max']}. Nearest snippet for a question with no answer: min "
            f"{noise['min']}, median {noise['median']}, max {noise['max']}.",
        ]
    misses = [r for r in modes["hybrid"]["results"] if r["recall_at_5"] < 1]
    if misses:
        lines += ["", "Hybrid queries missing a right answer in the top 5:", ""]
        for r in misses:
            got = ", ".join(r["ranked"][:3]) or "nothing"
            lines.append(f"- “{r['q']}” wants {', '.join(r['relevant'])}; top 3: {got}")
    return "\n".join(lines) + "\n"


def write_results(report: dict[str, Any], directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(report["timestamp"]).strftime("%Y%m%d-%H%M%S")
    stem = f"{stamp}_{re.sub(r'[^a-z0-9]+', '-', report['model'].lower()).strip('-')}"
    json_path, md_path = directory / f"{stem}.json", directory / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    md_path.write_text(render_markdown(report))
    return json_path, md_path


def main(argv: Sequence[str] | None = None, *, root: Path) -> int:
    """`root` is evals/search/: the dataset lives there and results go to root/results."""
    parser = argparse.ArgumentParser(description="Evaluate snippet search.")
    parser.add_argument("--max-distance", type=float, default=DEFAULT_MAX_DISTANCE)
    parser.add_argument("--repeats", type=int, default=3, help="timed runs per query")
    parser.add_argument(
        "--provider", choices=["settings", "fake"], default="settings",
        help="'fake' checks the plumbing without the model; its scores mean nothing",
    )  # fmt: skip
    parser.add_argument("--no-write", action="store_true", help="print only")
    args = parser.parse_args(argv)
    report = asyncio.run(_main(args, root))
    print(render_markdown(report))
    if not args.no_write:
        for path in write_results(report, root / "results"):
            print(f"wrote {path}")
    return 0


async def _main(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.db.session import get_engine, get_sessionmaker
    from app.services.ai.embeddings import (
        FakeEmbeddingProvider,
        check_embedding_config,
        get_embedding_provider,
    )

    settings = get_settings()
    provider: EmbeddingProvider
    if args.provider == "fake":
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
    else:
        check_embedding_config(settings)
        provider = get_embedding_provider()
    try:
        return await run(
            get_sessionmaker(),
            provider,
            load_dataset(root),
            max_distance=args.max_distance,
            repeats=args.repeats,
        )
    finally:
        await get_engine().dispose()
