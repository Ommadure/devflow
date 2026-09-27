"""ai usage and note chunks

- ai_usage: one row per LLM call, success or not (a failed call can still be billed).
  Indexed by (user_id, created_at) for the daily-quota check on every AI request.
- note_chunks: notes split into ~300-token passages at headings, each embedded, with a
  generated full-text column (heading weighted above content). "Ask your notes" retrieves
  and cites these. Cascades from both notes and users.
- notes.indexed_at: the note version its chunks reflect; behind updated_at = re-chunk.

Revision ID: 4626f0c8adee
Revises: 4c1e7b2d9a03
Create Date: 2026-09-27 16:16:58.537684
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '4626f0c8adee'
down_revision: str | None = '4c1e7b2d9a03'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('ai_usage',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('feature', sa.Text(), nullable=False),
    sa.Column('provider', sa.Text(), nullable=False),
    sa.Column('model', sa.Text(), nullable=False),
    sa.Column('prompt_version', sa.Text(), nullable=True),
    sa.Column('input_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('output_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), server_default=sa.text('0'), nullable=False),
    sa.Column('latency_ms', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('error_code', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("feature IN ('explain_code', 'auto_tag', 'ask_notes', 'explain_http_error', 'github_insights')", name=op.f('ck_ai_usage_feature_valid')),
    sa.CheckConstraint("status IN ('success', 'error', 'quota_exceeded')", name=op.f('ck_ai_usage_status_valid')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ai_usage_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_usage'))
    )
    op.create_index('ix_ai_usage_user_id_created_at', 'ai_usage', ['user_id', 'created_at'], unique=False)
    op.create_table('note_chunks',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('note_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('heading', sa.Text(), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.Text(), nullable=False),
    sa.Column('token_count', sa.Integer(), nullable=False),
    sa.Column('embedding', Vector(384), nullable=False),
    sa.Column('search_tsv', postgresql.TSVECTOR(), sa.Computed("setweight(to_tsvector('english', coalesce(heading, '')), 'A') || setweight(to_tsvector('english', content), 'B')", persisted=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['note_id'], ['notes.id'], name=op.f('fk_note_chunks_note_id_notes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_note_chunks_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_note_chunks')),
    sa.UniqueConstraint('note_id', 'chunk_index', name=op.f('uq_note_chunks_note_id'))
    )
    op.create_index('ix_note_chunks_embedding_hnsw', 'note_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_note_chunks_search_tsv', 'note_chunks', ['search_tsv'], unique=False, postgresql_using='gin')
    op.create_index('ix_note_chunks_user_id', 'note_chunks', ['user_id'], unique=False)
    op.add_column('notes', sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('notes', 'indexed_at')
    op.drop_index('ix_note_chunks_user_id', table_name='note_chunks')
    op.drop_index('ix_note_chunks_search_tsv', table_name='note_chunks', postgresql_using='gin')
    op.drop_index('ix_note_chunks_embedding_hnsw', table_name='note_chunks', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('note_chunks')
    op.drop_index('ix_ai_usage_user_id_created_at', table_name='ai_usage')
    op.drop_table('ai_usage')
