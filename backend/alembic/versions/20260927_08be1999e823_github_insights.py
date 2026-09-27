"""github insights

One row per user per week: the aggregated public GitHub activity (stats) and the AI
summary of it. Unique on (user_id, week_start), so re-running a week is an upsert.

Revision ID: 08be1999e823
Revises: 4626f0c8adee
Create Date: 2026-09-27 18:59:15.442597
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '08be1999e823'
down_revision: str | None = '4626f0c8adee'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('github_insights',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('github_username', sa.Text(), nullable=False),
    sa.Column('week_start', sa.Date(), nullable=False),
    sa.Column('stats', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_github_insights_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_github_insights')),
    sa.UniqueConstraint('user_id', 'week_start', name=op.f('uq_github_insights_user_id'))
    )


def downgrade() -> None:
    op.drop_table('github_insights')
