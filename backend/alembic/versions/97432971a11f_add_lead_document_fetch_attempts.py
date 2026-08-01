"""add lead document fetch attempts

Revision ID: 97432971a11f
Revises: 7c34945da69e
Create Date: 2026-08-01 14:04:03.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97432971a11f'
down_revision: Union[str, None] = '7c34945da69e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lead_documents', sa.Column('fetch_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('lead_documents', sa.Column('last_fetch_attempt_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('lead_documents', 'last_fetch_attempt_at')
    op.drop_column('lead_documents', 'fetch_attempts')
