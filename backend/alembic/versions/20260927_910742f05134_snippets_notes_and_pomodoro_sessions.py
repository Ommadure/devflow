"""snippets, notes and pomodoro sessions

The three user-owned modules. Every table cascades from users, and each has a composite
index that starts with user_id: it serves "this user's rows" filters and the keyset
pagination order at once.

Revision ID: 910742f05134
Revises: c9a96df0e5f1
Create Date: 2026-09-27 12:19:29.717855
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '910742f05134'
down_revision: str | None = 'c9a96df0e5f1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('notes',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.Text(), server_default=sa.text("''"), nullable=False),
    sa.Column('content', sa.Text(), server_default=sa.text("''"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notes_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notes'))
    )
    op.create_index('ix_notes_user_id_updated_at_id', 'notes', ['user_id', 'updated_at', 'id'], unique=False)
    op.create_table('pomodoro_sessions',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('duration_seconds', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('duration_seconds > 0', name=op.f('ck_pomodoro_sessions_duration_positive')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_pomodoro_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pomodoro_sessions'))
    )
    op.create_index('ix_pomodoro_sessions_user_id_completed_at_id', 'pomodoro_sessions', ['user_id', 'completed_at', 'id'], unique=False)
    op.create_table('snippets',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('language', sa.Text(), nullable=True),
    sa.Column('tags', sa.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('favorite', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_snippets_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_snippets'))
    )
    op.create_index('ix_snippets_user_id_created_at_id', 'snippets', ['user_id', 'created_at', 'id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_snippets_user_id_created_at_id', table_name='snippets')
    op.drop_table('snippets')
    op.drop_index('ix_pomodoro_sessions_user_id_completed_at_id', table_name='pomodoro_sessions')
    op.drop_table('pomodoro_sessions')
    op.drop_index('ix_notes_user_id_updated_at_id', table_name='notes')
    op.drop_table('notes')
