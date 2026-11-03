"""add escalation events

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-03 00:00:00.000000+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    escalation_status = postgresql.ENUM(
        'open', 'acknowledged', 'resolved',
        name='escalation_event_status',
    )
    escalation_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'escalation_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('detail', sa.Text(), nullable=False),
        sa.Column('context_package', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('severity_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column(
            'status',
            escalation_status,
            nullable=False,
            server_default='open',
        ),
        sa.Column('channels_sent', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_escalation_events_project_id', 'escalation_events', ['project_id'])
    op.create_index('ix_escalation_events_status', 'escalation_events', ['status'])
    op.create_index('ix_escalation_events_priority', 'escalation_events', ['priority'])
    op.create_index('ix_escalation_events_created_at', 'escalation_events', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_escalation_events_created_at', table_name='escalation_events')
    op.drop_index('ix_escalation_events_priority', table_name='escalation_events')
    op.drop_index('ix_escalation_events_status', table_name='escalation_events')
    op.drop_index('ix_escalation_events_project_id', table_name='escalation_events')
    op.drop_table('escalation_events')
    postgresql.ENUM(name='escalation_event_status').drop(op.get_bind(), checkfirst=True)
