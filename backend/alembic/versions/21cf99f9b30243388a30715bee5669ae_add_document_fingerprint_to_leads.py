"""add document_fingerprint to leads

Revision ID: 21cf99f9b302
Revises: 6ec871eedf20
Create Date: 2026-08-12 20:25:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "21cf99f9b302"
down_revision: Union[str, None] = "6ec871eedf20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("document_fingerprint", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "document_fingerprint")
