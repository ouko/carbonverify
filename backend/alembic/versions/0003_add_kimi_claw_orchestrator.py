"""Add Kimi Claw orchestrator models

Revision ID: 0003_orchestrator
Revises: 0002_file_uploads
Create Date: 2025-05-24 20:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_orchestrator"
down_revision = "0002_file_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AgentRun table
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("agent_type", sa.Enum("ingestion", "validation", "calculation", "reporting", "vvb_liaison", "quality_control", "client_success", name="agent_type"), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", "queued_for_review", name="agent_status"), server_default="pending", nullable=False),
        sa.Column("trigger_event", sa.String(100), nullable=False),
        sa.Column("input_data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("output_data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_agent_type", "agent_runs", ["agent_type"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    # OrchestratorEvent table
    op.create_table(
        "orchestrator_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("event_type", sa.Enum("state_transition", "agent_dispatch", "agent_complete", "confidence_check", "human_review_queued", "human_review_resolved", "auto_advance", "escalation", "error", name="orchestrator_event_type"), nullable=False),
        sa.Column("from_state", sa.String(50), nullable=True),
        sa.Column("to_state", sa.String(50), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("details", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_orchestrator_events_project_id", "orchestrator_events", ["project_id"])
    op.create_index("ix_orchestrator_events_event_type", "orchestrator_events", ["event_type"])

    # Add queue_item_type 'agent_review' to existing enum
    # NOTE: PostgreSQL enum alterations require special handling
    # For simplicity we add the new value. In production use op.execute with ALTER TYPE.
    op.execute("ALTER TYPE queue_item_type ADD VALUE IF NOT EXISTS 'agent_review'")

    # Add new columns to human_review_queue
    op.add_column("human_review_queue", sa.Column("priority_score", sa.Float(), nullable=True))
    op.add_column("human_review_queue", sa.Column("sla_deadline", sa.DateTime(), nullable=True))
    op.add_column("human_review_queue", sa.Column("context_json", postgresql.JSONB(), nullable=True))
    op.add_column("human_review_queue", sa.Column("suggested_action", sa.Text(), nullable=True))
    op.add_column("human_review_queue", sa.Column("confidence_gap", sa.Float(), nullable=True))
    op.add_column("human_review_queue", sa.Column("human_decision", sa.String(50), nullable=True))
    op.add_column("human_review_queue", sa.Column("learning_feedback", postgresql.JSONB(), nullable=True))
    op.add_column("human_review_queue", sa.Column("time_in_queue_seconds", sa.Integer(), nullable=True))
    op.add_column("human_review_queue", sa.Column("response_time_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("human_review_queue", "response_time_seconds")
    op.drop_column("human_review_queue", "time_in_queue_seconds")
    op.drop_column("human_review_queue", "learning_feedback")
    op.drop_column("human_review_queue", "human_decision")
    op.drop_column("human_review_queue", "confidence_gap")
    op.drop_column("human_review_queue", "suggested_action")
    op.drop_column("human_review_queue", "context_json")
    op.drop_column("human_review_queue", "sla_deadline")
    op.drop_column("human_review_queue", "priority_score")

    op.drop_index("ix_orchestrator_events_event_type", table_name="orchestrator_events")
    op.drop_index("ix_orchestrator_events_project_id", table_name="orchestrator_events")
    op.drop_table("orchestrator_events")

    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_type", table_name="agent_runs")
    op.drop_index("ix_agent_runs_project_id", table_name="agent_runs")
    op.drop_table("agent_runs")
