"""add_validation_engine_tables

Revision ID: 1e1e69dad168
Revises: c8e8775f56b9
Create Date: 2026-05-26 20:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1e1e69dad168'
down_revision: Union[str, None] = 'c8e8775f56b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENUMS = [
    "workflow_run_status",
    "workflow_step_type",
    "step_execution_status",
    "proof_type",
    "remediation_action",
    "remediation_status",
    "synthetic_actor_type",
    "escalation_level",
    "escalation_status",
]

TABLES = [
    "human_escalations",
    "validation_remediations",
    "validation_proofs",
    "validation_step_executions",
    "validation_run_transitions",
    "synthetic_actors",
    "validation_runs",
    "validation_workflows",
]


def _enum_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": name}
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


def _index_exists(table: str, name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename = :table AND indexname = :name"
        ),
        {"table": table, "name": name}
    )
    return result.scalar() is not None


def _create_enum(name: str, values: list) -> None:
    if not _enum_exists(name):
        values_str = ", ".join(f"'{v}'" for v in values)
        op.execute(sa.text(f"CREATE TYPE {name} AS ENUM ({values_str})"))


def upgrade() -> None:
    # Create enums first
    _create_enum("workflow_run_status", [
        "pending", "queued", "running", "step_validating", "proof_generating",
        "remediation_checking", "completed", "failed", "archived"
    ])
    _create_enum("workflow_step_type", [
        "http_request", "database_query", "service_call", "external_api",
        "notification", "dom_capture", "decision_gate", "wait", "parallel", "subflow"
    ])
    _create_enum("step_execution_status", [
        "pending", "running", "success", "failed", "skipped", "retried"
    ])
    _create_enum("proof_type", [
        "http_request", "http_response", "database_snapshot", "dom_capture",
        "service_input", "service_output", "external_api_request", "external_api_response",
        "filesystem_snapshot", "prometheus_metrics", "radix_anchor"
    ])
    _create_enum("remediation_action", [
        "retry", "rollback", "skip", "escalate", "patch", "circuit_break"
    ])
    _create_enum("remediation_status", [
        "attempted", "succeeded", "failed", "superseded"
    ])
    _create_enum("synthetic_actor_type", [
        "user", "admin", "service", "external_system", "browser"
    ])
    _create_enum("escalation_level", [
        "l1_operator", "l2_engineer", "l3_architect", "executive"
    ])
    _create_enum("escalation_status", [
        "pending", "acknowledged", "resolved", "timed_out"
    ])

    # validation_workflows
    if not _table_exists("validation_workflows"):
        op.create_table(
            'validation_workflows',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('version', sa.String(length=50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('active', sa.Boolean(), nullable=False),
            sa.Column('workflow_graph', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('graph_hash', sa.String(length=64), nullable=False),
            sa.Column('sla_seconds', sa.Integer(), nullable=True),
            sa.Column('human_gates_required', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_by', sa.UUID(), nullable=True),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name', 'version', name='uq_validation_workflow_name_version')
        )
        op.create_index('ix_validation_workflows_active', 'validation_workflows', ['active'], unique=False)
        op.create_index('ix_validation_workflows_name', 'validation_workflows', ['name'], unique=False)
        op.create_index('ix_validation_workflows_version', 'validation_workflows', ['version'], unique=False)

    # validation_runs
    if not _table_exists("validation_runs"):
        op.create_table(
            'validation_runs',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('workflow_id', sa.UUID(), nullable=False),
            sa.Column('project_id', sa.UUID(), nullable=True),
            sa.Column('triggered_by', sa.UUID(), nullable=True),
            sa.Column('trigger_event', sa.String(length=100), nullable=False),
            sa.Column('status', postgresql.ENUM(
                "pending", "queued", "running", "step_validating", "proof_generating",
                "remediation_checking", "completed", "failed", "archived",
                name='workflow_run_status', create_type=False
            ), nullable=False),
            sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('confidence_score', sa.Float(), nullable=True),
            sa.Column('merkle_root', sa.String(length=64), nullable=True),
            sa.Column('radix_tx_ref', sa.String(length=256), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('remediation_count', sa.Integer(), nullable=False),
            sa.Column('human_intervened', sa.Boolean(), nullable=False),
            sa.Column('awaiting_human_decision', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.ForeignKeyConstraint(['triggered_by'], ['users.id']),
            sa.ForeignKeyConstraint(['workflow_id'], ['validation_workflows.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_validation_runs_created_at', 'validation_runs', ['created_at'], unique=False)
        op.create_index('ix_validation_runs_project_id', 'validation_runs', ['project_id'], unique=False)
        op.create_index('ix_validation_runs_status', 'validation_runs', ['status'], unique=False)
        op.create_index('ix_validation_runs_triggered_by', 'validation_runs', ['triggered_by'], unique=False)
        op.create_index('ix_validation_runs_workflow_id', 'validation_runs', ['workflow_id'], unique=False)

    # synthetic_actors
    if not _table_exists("synthetic_actors"):
        op.create_table(
            'synthetic_actors',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('actor_type', postgresql.ENUM(
                "user", "admin", "service", "external_system", "browser",
                name='synthetic_actor_type', create_type=False
            ), nullable=False),
            sa.Column('profile_key', sa.String(length=100), nullable=False),
            sa.Column('markers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('behavior_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('context_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('active', sa.Boolean(), nullable=False),
            sa.Column('usage_count', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_synthetic_actors_actor_type', 'synthetic_actors', ['actor_type'], unique=False)
        op.create_index('ix_synthetic_actors_profile_key', 'synthetic_actors', ['profile_key'], unique=False)

    # validation_run_transitions
    if not _table_exists("validation_run_transitions"):
        op.create_table(
            'validation_run_transitions',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('run_id', sa.UUID(), nullable=False),
            sa.Column('from_state', sa.String(length=50), nullable=False),
            sa.Column('to_state', sa.String(length=50), nullable=False),
            sa.Column('triggered_by', sa.UUID(), nullable=True),
            sa.Column('actor_type', sa.String(length=50), nullable=False),
            sa.Column('synthetic_actor_id', sa.UUID(), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('transition_hash', sa.String(length=64), nullable=False),
            sa.Column('previous_hash', sa.String(length=64), nullable=True),
            sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.ForeignKeyConstraint(['run_id'], ['validation_runs.id']),
            sa.ForeignKeyConstraint(['synthetic_actor_id'], ['synthetic_actors.id']),
            sa.ForeignKeyConstraint(['triggered_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_validation_run_transitions_from_state', 'validation_run_transitions', ['from_state'], unique=False)
        op.create_index('ix_validation_run_transitions_occurred_at', 'validation_run_transitions', ['occurred_at'], unique=False)
        op.create_index('ix_validation_run_transitions_run_id', 'validation_run_transitions', ['run_id'], unique=False)
        op.create_index('ix_validation_run_transitions_to_state', 'validation_run_transitions', ['to_state'], unique=False)

    # validation_step_executions
    if not _table_exists("validation_step_executions"):
        op.create_table(
            'validation_step_executions',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('run_id', sa.UUID(), nullable=False),
            sa.Column('step_id', sa.String(length=100), nullable=False),
            sa.Column('step_index', sa.Integer(), nullable=False),
            sa.Column('step_type', postgresql.ENUM(
                "http_request", "database_query", "service_call", "external_api",
                "notification", "dom_capture", "decision_gate", "wait", "parallel", "subflow",
                name='workflow_step_type', create_type=False
            ), nullable=False),
            sa.Column('step_name', sa.String(length=255), nullable=False),
            sa.Column('status', postgresql.ENUM(
                "pending", "running", "success", "failed", "skipped", "retried",
                name='step_execution_status', create_type=False
            ), nullable=False),
            sa.Column('input_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('output_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('step_hash', sa.String(length=64), nullable=True),
            sa.Column('duration_ms', sa.Integer(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['run_id'], ['validation_runs.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_validation_step_executions_run_id', 'validation_step_executions', ['run_id'], unique=False)
        op.create_index('ix_validation_step_executions_status', 'validation_step_executions', ['status'], unique=False)
        op.create_index('ix_validation_step_executions_step_id', 'validation_step_executions', ['step_id'], unique=False)

    # validation_proofs
    if not _table_exists("validation_proofs"):
        op.create_table(
            'validation_proofs',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('run_id', sa.UUID(), nullable=False),
            sa.Column('step_execution_id', sa.UUID(), nullable=True),
            sa.Column('proof_type', postgresql.ENUM(
                "http_request", "http_response", "database_snapshot", "dom_capture",
                "service_input", "service_output", "external_api_request", "external_api_response",
                "filesystem_snapshot", "prometheus_metrics", "radix_anchor",
                name='proof_type', create_type=False
            ), nullable=False),
            sa.Column('proof_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('proof_hash', sa.String(length=64), nullable=False),
            sa.Column('merkle_leaf_index', sa.Integer(), nullable=True),
            sa.Column('s3_key', sa.String(length=1024), nullable=True),
            sa.Column('proof_size_bytes', sa.Integer(), nullable=False),
            sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['run_id'], ['validation_runs.id']),
            sa.ForeignKeyConstraint(['step_execution_id'], ['validation_step_executions.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_validation_proofs_proof_type', 'validation_proofs', ['proof_type'], unique=False)
        op.create_index('ix_validation_proofs_run_id', 'validation_proofs', ['run_id'], unique=False)
        op.create_index('ix_validation_proofs_step_execution_id', 'validation_proofs', ['step_execution_id'], unique=False)

    # validation_remediations
    if not _table_exists("validation_remediations"):
        op.create_table(
            'validation_remediations',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('run_id', sa.UUID(), nullable=False),
            sa.Column('step_execution_id', sa.UUID(), nullable=True),
            sa.Column('failure_condition', sa.Text(), nullable=False),
            sa.Column('action', postgresql.ENUM(
                "retry", "rollback", "skip", "escalate", "patch", "circuit_break",
                name='remediation_action', create_type=False
            ), nullable=False),
            sa.Column('action_params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('status', postgresql.ENUM(
                "attempted", "succeeded", "failed", "superseded",
                name='remediation_status', create_type=False
            ), nullable=False),
            sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['run_id'], ['validation_runs.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_validation_remediations_run_id', 'validation_remediations', ['run_id'], unique=False)
        op.create_index('ix_validation_remediations_status', 'validation_remediations', ['status'], unique=False)

    # human_escalations
    if not _table_exists("human_escalations"):
        op.create_table(
            'human_escalations',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('run_id', sa.UUID(), nullable=False),
            sa.Column('step_execution_id', sa.UUID(), nullable=True),
            sa.Column('escalation_reason', sa.Text(), nullable=False),
            sa.Column('severity_score', sa.Float(), nullable=False),
            sa.Column('level', postgresql.ENUM(
                "l1_operator", "l2_engineer", "l3_architect", "executive",
                name='escalation_level', create_type=False
            ), nullable=False),
            sa.Column('status', postgresql.ENUM(
                "pending", "acknowledged", "resolved", "timed_out",
                name='escalation_status', create_type=False
            ), nullable=False),
            sa.Column('assigned_to', sa.UUID(), nullable=True),
            sa.Column('context_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('human_decision', sa.String(length=50), nullable=True),
            sa.Column('human_notes', sa.Text(), nullable=True),
            sa.Column('sla_deadline', sa.DateTime(timezone=True), nullable=True),
            sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['assigned_to'], ['users.id']),
            sa.ForeignKeyConstraint(['run_id'], ['validation_runs.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_human_escalations_assigned_to', 'human_escalations', ['assigned_to'], unique=False)
        op.create_index('ix_human_escalations_level', 'human_escalations', ['level'], unique=False)
        op.create_index('ix_human_escalations_run_id', 'human_escalations', ['run_id'], unique=False)
        op.create_index('ix_human_escalations_status', 'human_escalations', ['status'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    for table in TABLES:
        if _table_exists(table):
            op.drop_table(table)

    # Drop enums
    for enum in ENUMS:
        if _enum_exists(enum):
            op.execute(sa.text(f"DROP TYPE IF EXISTS {enum}"))
