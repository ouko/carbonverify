"""add etag and last_modified to lead_documents

Revision ID: 6ec871eedf20
Revises: 7302c26e5365
Create Date: 2026-08-12 20:10:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6ec871eedf20"
down_revision: Union[str, None] = "7302c26e5365"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lead_documents", sa.Column("etag", sa.String(255), nullable=True))
    op.add_column("lead_documents", sa.Column("last_modified", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("lead_documents", "last_modified")
    op.drop_column("lead_documents", "etag")
