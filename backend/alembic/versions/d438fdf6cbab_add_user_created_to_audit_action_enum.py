"""add_user_created_to_audit_action_enum

Revision ID: d438fdf6cbab
Revises: 9c8caee4465a
Create Date: 2026-05-29 05:29:19.006175+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd438fdf6cbab'
down_revision: Union[str, None] = '9c8caee4465a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix user_invites.email to match the model (Text since encrypted types can't be migrated reliably)
    op.alter_column('user_invites', 'email',
               existing_type=sa.TEXT(),
               type_=sa.Text(),
               existing_nullable=False)

    # Add new values to audit_action_type enum
    op.execute("ALTER TYPE audit_action_type ADD VALUE IF NOT EXISTS 'user_created'")
    op.execute("ALTER TYPE audit_action_type ADD VALUE IF NOT EXISTS 'user_updated'")


def downgrade() -> None:
    # Enum values cannot be removed in PostgreSQL without recreating the type
    # Skipping enum downgrade for safety
    op.alter_column('user_invites', 'email',
               existing_type=sa.Text(),
               type_=sa.TEXT(),
               existing_nullable=False)
