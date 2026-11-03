"""add validation health snapshots

Revision ID: 0a1b2c3d4e5
Revises: f6a7b8c9d0e1
Create Date: 2026-11-03 00:00:00.000000+00:00

Stores the composite continuous-validation health score appended by the
15-minute synthetic-validation cycle. ``consecutive_below_threshold`` feeds
the deploy gate: 7+ consecutive snapshots below the threshold block deploys.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0a1b2c3d4e5'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'validation_health_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('run_stats', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            'consecutive_below_threshold',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )
    op.create_index(
        'ix_validation_health_snapshots_created_at',
        'validation_health_snapshots',
        ['created_at'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_validation_health_snapshots_created_at',
        table_name='validation_health_snapshots',
    )
    op.drop_table('validation_health_snapshots')
