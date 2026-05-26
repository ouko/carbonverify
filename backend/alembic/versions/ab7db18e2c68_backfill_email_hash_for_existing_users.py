"""backfill_email_hash_for_existing_users

Revision ID: ab7db18e2c68
Revises: 271490077edf, 1e1e69dad168
Create Date: 2026-05-26 22:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab7db18e2c68'
down_revision: Union[str, Sequence[str], None] = ('271490077edf', '1e1e69dad168')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column}
    )
    return result.scalar() is not None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": name}
    )
    return result.scalar() is not None


def upgrade() -> None:
    # If email_hash column doesn't exist yet (fresh DB case), create it
    if not _column_exists("users", "email_hash"):
        op.add_column(
            'users',
            sa.Column('email_hash', sa.String(length=64), nullable=True)
        )

    # Only proceed if users table exists
    if not _table_exists("users"):
        return

    # Backfill email_hash for users where it is NULL or empty
    # We use the same compute_searchable_hash logic from the app
    conn = op.get_bind()

    # Check if there are users with missing email_hash
    result = conn.execute(
        sa.text("SELECT id, email FROM users WHERE email_hash IS NULL OR email_hash = ''")
    )
    users_to_fix = result.fetchall()

    if not users_to_fix:
        return

    # Import the hash function from the app
    import sys
    import os
    backend_dir = os.path.join(os.path.dirname(__file__), '..', '..')
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    try:
        from app.core.encryption import compute_searchable_hash
    except Exception:
        # Fallback: compute raw SHA-256 if app code is unavailable
        import hashlib
        def compute_searchable_hash(value: str) -> str:
            return hashlib.sha256(value.encode("utf-8")).hexdigest()

    for user_id, email in users_to_fix:
        if email:
            email_hash = compute_searchable_hash(email)
            conn.execute(
                sa.text("UPDATE users SET email_hash = :hash WHERE id = :id"),
                {"hash": email_hash, "id": user_id}
            )

    # Make email_hash non-nullable if it isn't already
    conn.execute(
        sa.text(
            "ALTER TABLE users ALTER COLUMN email_hash SET NOT NULL"
        )
    )

    # Create index and unique constraint if they don't exist
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_users_email_hash'"
        )
    )
    if result.scalar() is None:
        op.create_index('ix_users_email_hash', 'users', ['email_hash'], unique=False)

    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_email_hash'"
        )
    )
    if result.scalar() is None:
        op.create_unique_constraint('uq_users_email_hash', 'users', ['email_hash'])


def downgrade() -> None:
    pass
