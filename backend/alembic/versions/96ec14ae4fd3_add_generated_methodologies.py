"""add generated methodologies

Revision ID: 96ec14ae4fd3
Revises: dca36f3e440d
Create Date: 2026-07-12 20:02:30.525081+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '96ec14ae4fd3'
down_revision: Union[str, None] = 'dca36f3e440d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generated_methodologies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sector", sa.String(100), nullable=False),
        sa.Column("activity_description", sa.Text(), nullable=False),
        sa.Column(
            "boundaries_json",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "data_sources_json",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("gap_analysis_json", postgresql.JSONB(), nullable=True),
        sa.Column("methodology_json", postgresql.JSONB(), nullable=True),
        sa.Column("quantification_scaffold_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_generated_methodologies_project_id",
        "generated_methodologies",
        ["project_id"],
    )
    op.create_index(
        "ix_generated_methodologies_status",
        "generated_methodologies",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generated_methodologies_status",
        table_name="generated_methodologies",
    )
    op.drop_index(
        "ix_generated_methodologies_project_id",
        table_name="generated_methodologies",
    )
    op.drop_table("generated_methodologies")
