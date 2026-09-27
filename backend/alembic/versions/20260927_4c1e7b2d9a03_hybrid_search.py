"""hybrid search: pgvector embeddings and a weighted full-text column on snippets

Written by hand: autogenerate can't create the extension or the helper function, and they
must exist before the columns that use them.

- `vector` extension (pgvector) and an `embedding vector(384)` column with an HNSW index.
- `search_tsv`, a *generated* tsvector: Postgres keeps it in sync with title, description,
  tags and code on every write, so the app can never forget to update it.
- Generated columns may only call IMMUTABLE functions, and array_to_string() is merely
  STABLE (it formats elements via their types' output functions). For a text[] the result
  can't vary, so a thin wrapper declared IMMUTABLE is safe — the standard workaround.
- search_words() appends a camelCase-split copy of the text ("useDebounce" → "use Debounce"):
  the default parser keeps identifiers whole, so without it "debounce" can't find
  `useDebounce`. regexp_replace() is immutable, so this one needs no workaround.
- Existing snippets start as embedding_status = 'pending'; the backfill job embeds them.

Revision ID: 4c1e7b2d9a03
Revises: 910742f05134
Create Date: 2026-09-27 13:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "4c1e7b2d9a03"
down_revision: str | None = "910742f05134"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_TSV = (
    "setweight(to_tsvector('english', search_words(title)), 'A') || "
    "setweight(to_tsvector('english', coalesce(description, '')), 'B') || "
    "setweight(to_tsvector('english', snippet_tags_text(tags)), 'B') || "
    "setweight(to_tsvector('simple', search_words(code)), 'C')"
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE FUNCTION snippet_tags_text(tags text[]) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE
        RETURN coalesce(array_to_string(tags, ' '), '')
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION search_words(value text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE
        RETURN coalesce(value, '') || ' '
            || regexp_replace(coalesce(value, ''), '([a-z0-9])([A-Z])', '\1 \2', 'g')
        """
    )
    op.add_column("snippets", sa.Column("content_hash", sa.Text(), nullable=True))
    op.add_column("snippets", sa.Column("embedding", Vector(384), nullable=True))
    op.add_column(
        "snippets",
        sa.Column(
            "embedding_status", sa.Text(), server_default=sa.text("'pending'"), nullable=False
        ),
    )
    op.add_column(
        "snippets", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "snippets",
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(SEARCH_TSV, persisted=True),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_snippets_embedding_status_valid"),
        "snippets",
        "embedding_status IN ('pending', 'ready', 'failed')",
    )
    op.create_index(
        "ix_snippets_embedding_hnsw",
        "snippets",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_snippets_search_tsv", "snippets", ["search_tsv"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_snippets_search_tsv", table_name="snippets")
    op.drop_index("ix_snippets_embedding_hnsw", table_name="snippets")
    op.drop_constraint(op.f("ck_snippets_embedding_status_valid"), "snippets", type_="check")
    op.drop_column("snippets", "search_tsv")
    op.drop_column("snippets", "embedded_at")
    op.drop_column("snippets", "embedding_status")
    op.drop_column("snippets", "embedding")
    op.drop_column("snippets", "content_hash")
    op.execute("DROP FUNCTION search_words(text)")
    op.execute("DROP FUNCTION snippet_tags_text(text[])")
    # The extension stays: other databases objects may use it, and dropping it is not
    # this migration's call.
