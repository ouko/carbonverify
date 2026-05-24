"""Initial migration

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "operator", "developer", "viewer", name="user_role"), nullable=False),
        sa.Column("mfa_enabled", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("hashed_password", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # Developers
    op.create_table(
        "developers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("location", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Projects
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("developer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("developers.id"), nullable=False),
        sa.Column("methodology", sa.Enum("TPDDTEC_v4", "VM0050", "VMR0006", "AMS-II.G", name="methodology"), nullable=False),
        sa.Column("crediting_period_start", sa.Date, nullable=False),
        sa.Column("crediting_period_end", sa.Date, nullable=False),
        sa.Column("status", sa.Enum("onboarding", "data_collection", "calculation", "review", "submitted", "verified", "monitoring", name="project_status"), server_default="onboarding", nullable=False),
        sa.Column("complexity_score", sa.Float, nullable=True),
        sa.Column("confidence_threshold", sa.Float, server_default=sa.text("0.85"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Data Sources
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source_type", sa.Enum("satellite", "iot", "mobile_survey", "document", "manual_entry", name="source_type"), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("raw_data", postgresql.JSONB, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("processed_data", postgresql.JSONB, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("validation_status", sa.Enum("pending", "valid", "flagged", "rejected", name="validation_status"), server_default="pending", nullable=False),
        sa.Column("validation_errors", sa.ARRAY(sa.Text), nullable=True),
        sa.Column("provenance", postgresql.JSONB, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Calculation Runs
    op.create_table(
        "calculation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("monitoring_period_start", sa.Date, nullable=False),
        sa.Column("monitoring_period_end", sa.Date, nullable=False),
        sa.Column("fNRB_value", sa.Float, nullable=True),
        sa.Column("emissions_reduction_tCO2e", sa.Float, nullable=True),
        sa.Column("uncertainty_95CI", sa.Float, nullable=True),
        sa.Column("leakage_assessment", postgresql.JSONB, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("methodology_compliance_score", sa.Float, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("status", sa.Enum("draft", "review_pending", "approved", "rejected", name="calculation_status"), server_default="draft", nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Reports
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("calculation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calculation_runs.id"), nullable=False),
        sa.Column("template_type", sa.Enum("GoldStandard_TPDDTEC", "Verra_VM0050", name="report_template_type"), nullable=False),
        sa.Column("draft_content", postgresql.JSONB, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("final_pdf", sa.String(512), nullable=True),
        sa.Column("status", sa.Enum("draft", "human_review", "approved", "submitted", "vvb_approved", "rejected", name="report_status"), server_default="draft", nullable=False),
        sa.Column("vvb_feedback", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Human Review Queue
    op.create_table(
        "human_review_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("item_type", sa.Enum("calculation", "report", "vvb_response", "data_anomaly", name="queue_item_type"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.Enum("pending", "in_review", "resolved", "escalated", name="queue_status"), server_default="pending", nullable=False),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.CheckConstraint("priority BETWEEN 1 AND 5", name="check_priority_range"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("human_review_queue")
    op.drop_table("reports")
    op.drop_table("calculation_runs")
    op.drop_table("data_sources")
    op.drop_table("projects")
    op.drop_table("developers")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS queue_status")
    op.execute("DROP TYPE IF EXISTS queue_item_type")
    op.execute("DROP TYPE IF EXISTS report_status")
    op.execute("DROP TYPE IF EXISTS report_template_type")
    op.execute("DROP TYPE IF EXISTS calculation_status")
    op.execute("DROP TYPE IF EXISTS validation_status")
    op.execute("DROP TYPE IF EXISTS source_type")
    op.execute("DROP TYPE IF EXISTS project_status")
    op.execute("DROP TYPE IF EXISTS methodology")
    op.execute("DROP TYPE IF EXISTS user_role")
