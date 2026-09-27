"""The evaluation's plumbing, with fake embeddings: it scores, reports and cleans up."""

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.evals import search as search_eval
from app.models import Snippet, User
from app.services.ai.embeddings import FakeEmbeddingProvider

DATASET = search_eval.Dataset.model_validate(
    {
        "snippets": [
            {"id": "debounce", "title": "Debounce helper", "code": "clearTimeout(t)"},
            {"id": "upsert", "title": "Upsert", "code": "ON CONFLICT DO UPDATE", "tags": ["sql"]},
        ],
        "queries": [
            {"q": "debounce", "kind": "keyword", "relevant": ["debounce"]},
            {"q": "stop firing too often", "kind": "intent", "relevant": ["debounce"]},
        ],
        "no_answer": ["banana bread"],
    }
)


async def test_scores_every_mode_and_deletes_its_user(
    sessionmaker: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    # The intent query embeds like the debounce snippet: a match only semantic search sees.
    embeddings = FakeEmbeddingProvider(aliases={"stop firing too often": "Debounce helper"})
    report = await search_eval.run(sessionmaker, embeddings, DATASET, repeats=1)

    keyword, hybrid = report["modes"]["keyword"], report["modes"]["hybrid"]
    assert keyword["by_kind"] == {
        "keyword": {"recall_at_5": 1.0, "mrr_at_10": 1.0},
        "intent": {"recall_at_5": 0.0, "mrr_at_10": 0.0},
    }
    assert hybrid["recall_at_5"] == 1.0
    assert hybrid["no_answer_with_results"] == 0
    assert [row["max_distance"] for row in report["cutoff_sweep"]] == list(search_eval.CUTOFFS)
    assert report["distances"]["nearest_for_no_answer"]["min"] > 0.4

    async with sessionmaker() as session:  # nothing left behind
        assert await session.scalar(select(func.count()).select_from(User)) == 0
        assert await session.scalar(select(func.count()).select_from(Snippet)) == 0

    json_path, md_path = search_eval.write_results(report, tmp_path)
    assert json_path.exists()
    markdown = md_path.read_text()
    assert "| hybrid | 1.00 | 1.00 |" in markdown
    assert "Semantic cut-off sweep" in markdown
