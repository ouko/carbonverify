"""add_missing_lead_status_enum_values

Revision ID: dfabefdb1273
Revises: 83f9a053933f
Create Date: 2026-05-25 14:46:54.794601+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'dfabefdb1273'
down_revision: Union[str, None] = '83f9a053933f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lead_project_status ADD VALUE 'under_certification'")
    op.execute("ALTER TYPE lead_project_status ADD VALUE 'request_for_issuance'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # Would require recreating the enum type.
    pass
