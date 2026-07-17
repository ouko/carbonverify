"""add ai_evaluation to workflow step type enum

Revision ID: c5bd1ba5368d
Revises: c2833757e4d3
Create Date: 2026-07-16 22:46:48.403000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c5bd1ba5368d"
down_revision: Union[str, None] = "c2833757e4d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new value to workflow_step_type enum
    op.execute("ALTER TYPE workflow_step_type ADD VALUE IF NOT EXISTS 'ai_evaluation'")


def downgrade() -> None:
    # Enum values cannot be removed in PostgreSQL without recreating the type
    # Skipping enum downgrade for safety
    pass
