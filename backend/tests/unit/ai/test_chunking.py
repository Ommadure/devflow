from app.services.ai.chunking import (
    OVERLAP_TOKENS,
    WINDOW_TOKENS,
    WORDS_PER_TOKEN,
    chunk_embedding_text,
    chunk_note,
)


def test_splits_at_headings_and_remembers_them() -> None:
    chunks = chunk_note("Intro.\n\n# Deploy\nRun migrations.\n\n## Rollback\nRevert the tag.")
    assert [(c.heading, c.content) for c in chunks] == [
        (None, "Intro."),
        ("Deploy", "Run migrations."),
        ("Rollback", "Revert the tag."),
    ]
    assert [c.index for c in chunks] == [0, 1, 2]


def test_hash_lines_inside_code_fences_are_not_headings() -> None:
    [chunk] = chunk_note("# Script\n```python\n# a comment, not a heading\nprint(1)\n```")
    assert chunk.heading == "Script"
    assert "# a comment" in chunk.content


def test_empty_sections_and_empty_notes_produce_nothing() -> None:
    assert chunk_note("") == []
    assert [c.heading for c in chunk_note("# Empty\n\n# Full\ntext")] == ["Full"]


def test_long_sections_become_overlapping_windows() -> None:
    words = [f"w{i}" for i in range(500)]
    chunks = chunk_note("# Long\n" + " ".join(words))
    size = round(WINDOW_TOKENS * WORDS_PER_TOKEN)
    overlap = round(OVERLAP_TOKENS * WORDS_PER_TOKEN)
    assert len(chunks) == 3
    first, second = chunks[0].content.split(), chunks[1].content.split()
    assert len(first) == size
    assert first[-overlap:] == second[:overlap]  # the seam appears whole in both
    assert chunks[-1].content.split()[-1] == "w499"  # nothing lost at the end
    assert all(c.heading == "Long" for c in chunks)


def test_embedding_text_carries_the_note_title_and_heading() -> None:
    [chunk] = chunk_note("# Deploy\nRun migrations.")
    assert chunk_embedding_text("Runbook", chunk) == "Runbook\nDeploy\nRun migrations."
