"""Ranking metrics for the search evaluation.

Recall@k: of the snippets a person would accept, how many are in the top k.
Reciprocal rank@k: 1 / the position of the first acceptable snippet (0 if none in the top k);
its mean over queries is MRR. Recall says "is it on the first screen", MRR "how high".
"""

import math
from collections.abc import Collection, Sequence


def recall_at(ranked: Sequence[str], relevant: Collection[str], k: int) -> float:
    return len(set(ranked[:k]) & set(relevant)) / len(relevant)


def reciprocal_rank(ranked: Sequence[str], relevant: Collection[str], k: int) -> float:
    for position, item in enumerate(ranked[:k], start=1):
        if item in relevant:
            return 1 / position
    return 0.0


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile: always a value that was actually measured."""
    ordered = sorted(values)
    return ordered[max(math.ceil(p / 100 * len(ordered)) - 1, 0)]


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
