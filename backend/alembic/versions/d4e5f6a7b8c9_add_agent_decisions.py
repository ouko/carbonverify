"""add agent decisions audit trail

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-03 00:00:00.000000+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_decisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agent_type', sa.String(length=100), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=False),
        sa.Column('input_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('context_package', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('prev_hash', sa.String(length=64), nullable=True),
        sa.Column('record_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('review_queue_item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['review_queue_item_id'], ['human_review_queue.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('decision_id', name='uq_agent_decisions_decision_id'),
    )
    op.create_index('ix_agent_decisions_project_id', 'agent_decisions', ['project_id'])
    op.create_index('ix_agent_decisions_action', 'agent_decisions', ['action'])
    op.create_index('ix_agent_decisions_created_at', 'agent_decisions', ['created_at'])

    op.add_column(
        'human_review_queue',
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_human_review_queue_decision_id',
        'human_review_queue', 'agent_decisions',
        ['decision_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_human_review_queue_decision_id', 'human_review_queue', type_='foreignkey')
    op.drop_column('human_review_queue', 'decision_id')
    op.drop_index('ix_agent_decisions_created_at', table_name='agent_decisions')
    op.drop_index('ix_agent_decisions_action', table_name='agent_decisions')
    op.drop_index('ix_agent_decisions_project_id', table_name='agent_decisions')
    op.drop_table('agent_decisions')
