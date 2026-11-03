"""add knowledge base and learning loop tables

Revision ID: 1b2c3d4e5f6
Revises: 0a1b2c3d4e5
Create Date: 2026-11-03 00:00:00.000000+00:00

Creates the Phase 5 tables:

- ``methodology_documents`` — ingested methodology texts (registry-classified).
- ``knowledge_chunks`` — searchable chunks with stored embeddings.
- ``learning_reports`` — persisted learning-loop reports (weekly retraining briefs).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1b2c3d4e5f6'
down_revision: Union[str, None] = '0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'methodology_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('registry', sa.String(length=50), nullable=False),
        sa.Column('methodology_id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_methodology_documents_registry', 'methodology_documents', ['registry']
    )
    op.create_index(
        'ix_methodology_documents_methodology_id', 'methodology_documents', ['methodology_id']
    )

    op.create_table(
        'knowledge_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'document_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('methodology_documents.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_knowledge_chunks_document_id', 'knowledge_chunks', ['document_id']
    )

    op.create_table(
        'learning_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('report_type', sa.String(length=50), nullable=False),
        sa.Column('report', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_learning_reports_report_type', 'learning_reports', ['report_type']
    )
    op.create_index(
        'ix_learning_reports_created_at', 'learning_reports', ['created_at']
    )


def downgrade() -> None:
    op.drop_index('ix_learning_reports_created_at', table_name='learning_reports')
    op.drop_index('ix_learning_reports_report_type', table_name='learning_reports')
    op.drop_table('learning_reports')

    op.drop_index('ix_knowledge_chunks_document_id', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')

    op.drop_index(
        'ix_methodology_documents_methodology_id', table_name='methodology_documents'
    )
    op.drop_index('ix_methodology_documents_registry', table_name='methodology_documents')
    op.drop_table('methodology_documents')
