"""Database models for the Workflow Validation Engine."""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    String,
    Text,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
    Integer,
    Index,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


# ─── State Machine Enums ──────────────────────────────────────────────────────

class WorkflowRunStatus(str, PyEnum):
    pending = "pending"
    queued = "queued"
    running = "running"
    step_validating = "step_validating"
    proof_generating = "proof_generating"
    remediation_checking = "remediation_checking"
    completed = "completed"
    failed = "failed"
    archived = "archived"


class WorkflowStepType(str, PyEnum):
    http_request = "http_request"
    database_query = "database_query"
    service_call = "service_call"
    external_api = "external_api"
    notification = "notification"
    dom_capture = "dom_capture"
    decision_gate = "decision_gate"
    wait = "wait"
    parallel = "parallel"
    subflow = "subflow"


class StepExecutionStatus(str, PyEnum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"
    retried = "retried"


class ProofType(str, PyEnum):
    http_request = "http_request"
    http_response = "http_response"
    database_snapshot = "database_snapshot"
    dom_capture = "dom_capture"
    service_input = "service_input"
    service_output = "service_output"
    external_api_request = "external_api_request"
    external_api_response = "external_api_response"
    filesystem_snapshot = "filesystem_snapshot"
    prometheus_metrics = "prometheus_metrics"
    radix_anchor = "radix_anchor"


class RemediationAction(str, PyEnum):
    retry = "retry"
    rollback = "rollback"
    skip = "skip"
    escalate = "escalate"
    patch = "patch"
    circuit_break = "circuit_break"


class RemediationStatus(str, PyEnum):
    attempted = "attempted"
    succeeded = "succeeded"
    failed = "failed"
    superseded = "superseded"


class SyntheticActorType(str, PyEnum):
    user = "user"
    admin = "admin"
    service = "service"
    external_system = "external_system"
    browser = "browser"


class EscalationLevel(str, PyEnum):
    l1_operator = "l1_operator"
    l2_engineer = "l2_engineer"
    l3_architect = "l3_architect"
    executive = "executive"


class EscalationStatus(str, PyEnum):
    pending = "pending"
    acknowledged = "acknowledged"
    resolved = "resolved"
    timed_out = "timed_out"


# ─── Workflow Definition ──────────────────────────────────────────────────────

class ValidationWorkflow(Base):
    """A JSON-defined workflow graph stored in the database."""

    __tablename__ = "validation_workflows"

    __table_args__ = (
        Index("ix_validation_workflows_name", "name"),
        Index("ix_validation_workflows_active", "active"),
        Index("ix_validation_workflows_version", "version"),
        UniqueConstraint("name", "version", name="uq_validation_workflow_name_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    workflow_graph: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Hash of the workflow_graph for integrity verification
    graph_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Expected SLA for this workflow in seconds
    sla_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Whether this workflow requires human approval at decision gates
    human_gates_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    runs: Mapped[List["ValidationRun"]] = relationship(
        "ValidationRun", back_populates="workflow"
    )


# ─── Validation Run ───────────────────────────────────────────────────────────

class ValidationRun(Base):
    """A single execution instance of a validation workflow."""

    __tablename__ = "validation_runs"

    __table_args__ = (
        Index("ix_validation_runs_workflow_id", "workflow_id"),
        Index("ix_validation_runs_status", "status"),
        Index("ix_validation_runs_project_id", "project_id"),
        Index("ix_validation_runs_created_at", "created_at"),
        Index("ix_validation_runs_triggered_by", "triggered_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_workflows.id"), nullable=False
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    triggered_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[WorkflowRunStatus] = mapped_column(
        Enum(WorkflowRunStatus, name="workflow_run_status"),
        default=WorkflowRunStatus.pending,
        nullable=False,
    )
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Overall confidence score for this run (0.0 - 1.0)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Merkle root hash of all step proofs
    merkle_root: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Radix ledger transaction reference for the Merkle root anchor
    radix_tx_ref: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # Unix timestamp when the run started
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Unix timestamp when the run completed
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Unix timestamp when the run was archived
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Number of remediation attempts made
    remediation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Whether human intervention was required
    human_intervened: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Whether the run is currently in a decision gate awaiting human input
    awaiting_human_decision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    workflow: Mapped["ValidationWorkflow"] = relationship(
        "ValidationWorkflow", back_populates="runs"
    )
    step_executions: Mapped[List["ValidationStepExecution"]] = relationship(
        "ValidationStepExecution", back_populates="run", order_by="ValidationStepExecution.step_index"
    )
    transitions: Mapped[List["ValidationRunTransition"]] = relationship(
        "ValidationRunTransition", back_populates="run", order_by="ValidationRunTransition.occurred_at"
    )
    proofs: Mapped[List["ValidationProof"]] = relationship(
        "ValidationProof", back_populates="run"
    )
    remediations: Mapped[List["ValidationRemediation"]] = relationship(
        "ValidationRemediation", back_populates="run"
    )
    escalations: Mapped[List["HumanEscalation"]] = relationship(
        "HumanEscalation", back_populates="run"
    )


# ─── Validation Run Transitions (Immutable Audit Log) ─────────────────────────

class ValidationRunTransition(Base):
    """Immutable record of every state transition. Serves as the audit trail."""

    __tablename__ = "validation_run_transitions"

    __table_args__ = (
        Index("ix_validation_run_transitions_run_id", "run_id"),
        Index("ix_validation_run_transitions_from_state", "from_state"),
        Index("ix_validation_run_transitions_to_state", "to_state"),
        Index("ix_validation_run_transitions_occurred_at", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(String(50), nullable=False)
    to_state: Mapped[str] = mapped_column(String(50), nullable=False)
    triggered_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # Actor type: 'system', 'user', 'synthetic_actor', 'remediation_engine'
    actor_type: Mapped[str] = mapped_column(String(50), default="system", nullable=False)
    # ID of the synthetic actor if applicable
    synthetic_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("synthetic_actors.id"), nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # SHA-256 hash of this transition record (for chain integrity)
    transition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Hash of the previous transition in this run (builds a chain)
    previous_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    run: Mapped["ValidationRun"] = relationship("ValidationRun", back_populates="transitions")


# ─── Step Execution ───────────────────────────────────────────────────────────

class ValidationStepExecution(Base):
    """Individual step execution within a validation run."""

    __tablename__ = "validation_step_executions"

    __table_args__ = (
        Index("ix_validation_step_executions_run_id", "run_id"),
        Index("ix_validation_step_executions_status", "status"),
        Index("ix_validation_step_executions_step_id", "step_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=False
    )
    step_id: Mapped[str] = mapped_column(String(100), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[WorkflowStepType] = mapped_column(
        Enum(WorkflowStepType, name="workflow_step_type"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[StepExecutionStatus] = mapped_column(
        Enum(StepExecutionStatus, name="step_execution_status"),
        default=StepExecutionStatus.pending,
        nullable=False,
    )
    input_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # SHA-256 hash of the step's input + output + metadata
    step_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Execution duration in milliseconds
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Number of retry attempts for this step
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped["ValidationRun"] = relationship("ValidationRun", back_populates="step_executions")
    proofs: Mapped[List["ValidationProof"]] = relationship(
        "ValidationProof", back_populates="step_execution"
    )


# ─── Validation Proof ─────────────────────────────────────────────────────────

class ValidationProof(Base):
    """Cryptographic proof artifact captured during workflow execution."""

    __tablename__ = "validation_proofs"

    __table_args__ = (
        Index("ix_validation_proofs_run_id", "run_id"),
        Index("ix_validation_proofs_step_execution_id", "step_execution_id"),
        Index("ix_validation_proofs_proof_type", "proof_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=False
    )
    step_execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_step_executions.id"), nullable=True
    )
    proof_type: Mapped[ProofType] = mapped_column(
        Enum(ProofType, name="proof_type"), nullable=False
    )
    # The actual proof data (structured JSON, may contain base64-encoded binaries)
    proof_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    # SHA-256 hash of the proof_data JSON canonicalized representation
    proof_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Merkle leaf index within the run's proof tree
    merkle_leaf_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # S3 key if proof data is stored externally (for large captures)
    s3_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    # Size in bytes of the proof data
    proof_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped["ValidationRun"] = relationship("ValidationRun", back_populates="proofs")
    step_execution: Mapped[Optional["ValidationStepExecution"]] = relationship(
        "ValidationStepExecution", back_populates="proofs"
    )


# ─── Synthetic Actor ──────────────────────────────────────────────────────────

class SyntheticActor(Base):
    """A synthetic persona used during workflow validation."""

    __tablename__ = "synthetic_actors"

    __table_args__ = (
        Index("ix_synthetic_actors_actor_type", "actor_type"),
        Index("ix_synthetic_actors_profile_key", "profile_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Human-readable name of this actor (e.g., "test_user_rural_kenya")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_type: Mapped[SyntheticActorType] = mapped_column(
        Enum(SyntheticActorType, name="synthetic_actor_type"), nullable=False
    )
    # A key identifying the behavioral profile (e.g., "impatient_mobile_user")
    profile_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # Identifiable markers injected into this actor's interactions
    markers: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Behavioral configuration (typing speed, navigation patterns, etc.)
    behavior_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Static context data (e.g., test credentials, fake PII)
    context_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Whether this actor is currently available for use
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Number of times this actor has been used
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ─── Validation Remediation ───────────────────────────────────────────────────

class ValidationRemediation(Base):
    """Auto-remediation attempt for a failed step or run."""

    __tablename__ = "validation_remediations"

    __table_args__ = (
        Index("ix_validation_remediations_run_id", "run_id"),
        Index("ix_validation_remediations_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=False
    )
    step_execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_step_executions.id"), nullable=True
    )
    # The failure condition that triggered remediation
    failure_condition: Mapped[str] = mapped_column(Text, nullable=False)
    # The remediation action taken
    action: Mapped[RemediationAction] = mapped_column(
        Enum(RemediationAction, name="remediation_action"), nullable=False
    )
    # Action-specific parameters
    action_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[RemediationStatus] = mapped_column(
        Enum(RemediationStatus, name="remediation_status"),
        default=RemediationStatus.attempted,
        nullable=False,
    )
    # Result of the remediation attempt
    result_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["ValidationRun"] = relationship("ValidationRun", back_populates="remediations")


# ─── Human Escalation ─────────────────────────────────────────────────────────

class HumanEscalation(Base):
    """Human intervention gate/escalation record."""

    __tablename__ = "human_escalations"

    __table_args__ = (
        Index("ix_human_escalations_run_id", "run_id"),
        Index("ix_human_escalations_status", "status"),
        Index("ix_human_escalations_assigned_to", "assigned_to"),
        Index("ix_human_escalations_level", "level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=False
    )
    step_execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_step_executions.id"), nullable=True
    )
    # The condition that triggered escalation
    escalation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    # Severity score (0.0 - 1.0)
    severity_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    level: Mapped[EscalationLevel] = mapped_column(
        Enum(EscalationLevel, name="escalation_level"),
        default=EscalationLevel.l1_operator,
        nullable=False,
    )
    status: Mapped[EscalationStatus] = mapped_column(
        Enum(EscalationStatus, name="escalation_status"),
        default=EscalationStatus.pending,
        nullable=False,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # Context data for the human reviewer
    context_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Human's decision
    human_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Human's notes
    human_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # SLA deadline for response
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the escalation was acknowledged
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the escalation was resolved
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped["ValidationRun"] = relationship("ValidationRun", back_populates="escalations")
