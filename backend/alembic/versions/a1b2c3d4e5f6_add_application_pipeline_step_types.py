"""add application pipeline step types to workflow_step_type enum

Revision ID: a1b2c3d4e5f6
Revises: 77a8219f7670
Create Date: 2026-08-28 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "77a8219f7670"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new values to workflow_step_type enum
    op.execute("ALTER TYPE workflow_step_type ADD VALUE IF NOT EXISTS 'application_intake'")
    op.execute("ALTER TYPE workflow_step_type ADD VALUE IF NOT EXISTS 'document_collection'")
    op.execute("ALTER TYPE workflow_step_type ADD VALUE IF NOT EXISTS 'document_ai_classification'")


def downgrade() -> None:
    # Enum values cannot be removed in PostgreSQL without recreating the type
    # Skipping enum downgrade for safety
    pass
