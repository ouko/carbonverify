"""add application queue item type

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-06 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE queue_item_type ADD VALUE IF NOT EXISTS 'application'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # Would require recreating the enum type.
    pass
