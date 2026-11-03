"""add remediation tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-03 00:00:00.000000+00:00

Creates the shared self-healing remediation engine tables:

- ``remediation_rules`` — named strategies per failure category.
- ``remediation_attempts`` — hashed audit trail of every remediation attempt.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'remediation_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('rule_key', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('strategy', sa.String(length=50), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('rule_key', name='uq_remediation_rules_rule_key'),
    )
    op.create_index('ix_remediation_rules_category', 'remediation_rules', ['category'])

    op.create_table(
        'remediation_attempts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('rule_key', sa.String(length=100), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.String(length=255), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='attempted'),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('before_state_hash', sa.String(length=64), nullable=False),
        sa.Column('after_state_hash', sa.String(length=64), nullable=True),
        sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    )
    op.create_index(
        'ix_remediation_attempts_rule_key', 'remediation_attempts', ['rule_key']
    )
    op.create_index(
        'ix_remediation_attempts_target',
        'remediation_attempts',
        ['target_type', 'target_id'],
    )
    op.create_index(
        'ix_remediation_attempts_status', 'remediation_attempts', ['status']
    )
    op.create_index(
        'ix_remediation_attempts_created_at', 'remediation_attempts', ['created_at']
    )


def downgrade() -> None:
    op.drop_index('ix_remediation_attempts_created_at', table_name='remediation_attempts')
    op.drop_index('ix_remediation_attempts_status', table_name='remediation_attempts')
    op.drop_index('ix_remediation_attempts_target', table_name='remediation_attempts')
    op.drop_index('ix_remediation_attempts_rule_key', table_name='remediation_attempts')
    op.drop_table('remediation_attempts')

    op.drop_index('ix_remediation_rules_category', table_name='remediation_rules')
    op.drop_table('remediation_rules')
