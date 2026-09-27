from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evals.metrics import mean, percentile, recall_at, reciprocal_rank
from app.evals.search import Dataset, load_dataset

DATASET = Path(__file__).resolve().parents[4] / "evals" / "search"


def test_recall_counts_every_relevant_item_in_the_top_k() -> None:
    assert recall_at(["a", "x", "b", "y"], {"a", "b"}, 5) == 1.0
    assert recall_at(["a", "x", "b"], {"a", "b"}, 2) == 0.5
    assert recall_at([], {"a"}, 5) == 0.0


def test_reciprocal_rank_is_one_over_the_first_hit() -> None:
    assert reciprocal_rank(["x", "a", "b"], {"a", "b"}, 10) == 0.5
    assert reciprocal_rank(["x", "y", "a"], {"a"}, 2) == 0.0  # beyond k counts as a miss


def test_percentile_is_a_measured_value() -> None:
    values = [float(v) for v in range(1, 101)]
    assert (percentile(values, 50), percentile(values, 95)) == (50.0, 95.0)
    assert percentile([7.0], 95) == 7.0
    assert mean([]) == 0.0


def test_the_committed_dataset_is_consistent() -> None:
    dataset = load_dataset(DATASET)
    assert len(dataset.snippets) >= 60 and len(dataset.queries) >= 30
    assert {q.kind for q in dataset.queries} == {"keyword", "intent", "mixed"}


def test_a_query_pointing_at_a_missing_snippet_is_rejected() -> None:
    snippet = {"id": "a", "title": "t", "code": "c"}
    with pytest.raises(ValidationError, match="unknown snippets"):
        Dataset.model_validate(
            {"snippets": [snippet], "queries": [{"q": "x", "kind": "intent", "relevant": ["b"]}]}
        )
    with pytest.raises(ValidationError, match="duplicate"):
        Dataset.model_validate({"snippets": [snippet, snippet], "queries": []})
    with pytest.raises(ValidationError):  # a query needs at least one right answer
        Dataset.model_validate(
            {"snippets": [snippet], "queries": [{"q": "x", "kind": "intent", "relevant": []}]}
        )
