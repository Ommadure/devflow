"""What a snippet's embedding is made from, and the hash that makes re-embedding idempotent."""

import hashlib

from app.models import Snippet

# bge-small reads at most 512 tokens (FastEmbed truncates the rest). ~4 characters per token
# in code, so cutting at 4,000 characters avoids tokenising text that would be thrown away.
MAX_CHARS = 4_000


def embedding_text(snippet: Snippet) -> str:
    """Title and description first: they state intent in plain words, which is what
    queries look like. Code last, since it's the part most likely to be truncated."""
    parts = [
        snippet.title,
        snippet.description or "",
        " ".join(snippet.tags),
        snippet.language or "",
        snippet.code,
    ]
    return "\n".join(part for part in parts if part)[:MAX_CHARS]


def content_hash(text: str, model_name: str) -> str:
    """Includes the model: switching models must re-embed everything."""
    return hashlib.sha256(f"{model_name}\n{text}".encode()).hexdigest()
