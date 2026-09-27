"""Split a markdown note into passages for "ask your notes" (spec §11.5).

1. Split at headings, so a passage is about one topic and knows its heading (for citations).
   `#` lines inside ``` code fences are comments, not headings.
2. Split long sections into ~300-token windows that overlap by ~50 tokens, so a sentence
   cut at a window boundary still appears whole in one of them.

Tokens are estimated from words (≈ 0.75 words per token in English): exact counts would
need the model's tokenizer, and a passage 10% over or under target changes nothing.
"""

import re
from dataclasses import dataclass

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")

WINDOW_TOKENS = 300
OVERLAP_TOKENS = 50
WORDS_PER_TOKEN = 0.75


@dataclass(frozen=True)
class Chunk:
    index: int
    heading: str | None
    content: str
    token_count: int


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text.split()) / WORDS_PER_TOKEN))


def _sections(content: str) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    in_fence = False
    for line in content.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        heading = None if in_fence else HEADING.match(line)
        if heading:
            sections.append((heading.group(2).strip(), []))
        else:
            sections[-1][1].append(line)
    return [(heading, "\n".join(lines).strip()) for heading, lines in sections]


def _windows(text: str) -> list[str]:
    words = text.split()
    size = round(WINDOW_TOKENS * WORDS_PER_TOKEN)
    step = size - round(OVERLAP_TOKENS * WORDS_PER_TOKEN)
    if len(words) <= size:
        return [text]
    # Windows lose the original line breaks; fine for retrieval and for the prompt.
    return [
        " ".join(words[start : start + size])
        for start in range(0, len(words) - (size - step), step)
    ]


def chunk_note(content: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for heading, body in _sections(content):
        if not body:
            continue  # a heading with nothing under it has nothing to retrieve
        for window in _windows(body):
            chunks.append(Chunk(len(chunks), heading, window, estimate_tokens(window)))
    return chunks


def chunk_embedding_text(note_title: str, chunk: Chunk) -> str:
    """What gets embedded: the passage plus where it lives, so "the deploy steps" can match
    a passage under the heading "Deploy" in a note titled "Runbook"."""
    return "\n".join(part for part in (note_title, chunk.heading, chunk.content) if part)
