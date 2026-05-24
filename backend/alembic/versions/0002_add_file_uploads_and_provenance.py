"""Add file_uploads table and provenance enhancements

Revision ID: 0002_file_uploads
Revises: 0001_initial
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_file_uploads"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add confidence_score to data_sources
    op.add_column(
        "data_sources",
        sa.Column("confidence_score", sa.Float, nullable=True)
    )

    # Create file_uploads table
    op.create_table(
        "file_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("detected_type", sa.Enum("excel", "csv", "pdf", "image", "unknown", name="detected_file_type"), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("s3_key", sa.String(1024), nullable=False),
        sa.Column("s3_bucket", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("file_hash_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.Enum("uploaded", "processing", "completed", "failed", name="file_upload_status"), server_default="uploaded", nullable=False),
        sa.Column("processing_result", postgresql.JSONB, nullable=True),
        sa.Column("validation_errors", sa.ARRAY(sa.Text), nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("provenance", postgresql.JSONB, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create index on file_uploads project_id
    op.create_index("ix_file_uploads_project_id", "file_uploads", ["project_id"])
    op.create_index("ix_file_uploads_status", "file_uploads", ["status"])


def downgrade() -> None:
    op.drop_index("ix_file_uploads_status", table_name="file_uploads")
    op.drop_index("ix_file_uploads_project_id", table_name="file_uploads")
    op.drop_table("file_uploads")
    op.execute("DROP TYPE IF EXISTS file_upload_status")
    op.execute("DROP TYPE IF EXISTS detected_file_type")
    op.drop_column("data_sources", "confidence_score")
