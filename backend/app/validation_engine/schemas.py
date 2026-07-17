"""Pydantic schemas for JSON-defined workflow graphs and API payloads."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from app.validation_engine.models import (
    EscalationLevel,
    EscalationStatus,
    ProofType,
    RemediationAction,
    RemediationStatus,
    StepExecutionStatus,
    SyntheticActorType,
    WorkflowRunStatus,
    WorkflowStepType,
)


# ─── Workflow Graph JSON Schema ───────────────────────────────────────────────

class RetryPolicy(BaseModel):
    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    initial_delay_ms: int = Field(default=500, ge=0)
    retry_on: List[str] = Field(default_factory=lambda: ["timeout", "connection_error", "rate_limit"])


class CircuitBreakerConfig(BaseModel):
    failure_threshold: int = Field(default=5, ge=1)
    recovery_timeout_ms: int = Field(default=30000, ge=1000)
    half_open_max_calls: int = Field(default=3, ge=1)


class HttpStepConfig(BaseModel):
    method: str = Field(..., pattern=r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$")
    url: str = Field(..., min_length=1)
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    timeout_ms: int = Field(default=30000, ge=100)
    expected_status_codes: List[int] = Field(default_factory=lambda: [200])
    capture_response: bool = Field(default=True)


class DatabaseQueryConfig(BaseModel):
    query: str = Field(..., min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)
    expected_row_count: Optional[int] = None
    snapshot_result: bool = Field(default=True)


class ServiceCallConfig(BaseModel):
    service_name: str = Field(..., min_length=1)
    method_name: str = Field(..., min_length=1)
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    capture_io: bool = Field(default=True)


class ExternalApiConfig(BaseModel):
    provider: str = Field(..., min_length=1)
    endpoint: str = Field(..., min_length=1)
    method: str = Field(default="GET", pattern=r"^(GET|POST|PUT|DELETE|PATCH)$")
    params: Dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=30000, ge=100)


class NotificationConfig(BaseModel):
    channel: str = Field(..., pattern=r"^(email|sms|whatsapp|slack|webhook|in_app)$")
    template_id: Optional[str] = None
    recipients: List[str] = Field(default_factory=list)
    subject: Optional[str] = None
    body: Optional[str] = None
    priority: str = Field(default="normal", pattern=r"^(low|normal|high|critical)$")


class DomCaptureConfig(BaseModel):
    selector: Optional[str] = None
    full_page: bool = Field(default=False)
    capture_screenshot: bool = Field(default=True)
    capture_html: bool = Field(default=True)
    viewport_width: int = Field(default=1280, ge=320)
    viewport_height: int = Field(default=720, ge=240)


class DecisionGateConfig(BaseModel):
    condition_expression: str = Field(..., min_length=1)
    # Human approval required if condition evaluates to true
    require_human_approval: bool = Field(default=False)
    # Auto-approve if confidence > threshold
    auto_approve_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    timeout_seconds: int = Field(default=300, ge=10)
    escalation_level: EscalationLevel = Field(default=EscalationLevel.l1_operator)


class AiEvaluationConfig(BaseModel):
    # The evaluation prompt sent to the AI
    prompt: str = Field(..., min_length=1, max_length=8000)
    # Optional structured input data from the workflow context
    input_data: Dict[str, Any] = Field(default_factory=dict)
    # Expected JSON schema for the AI response (descriptive, not enforced by DB)
    expected_output_schema: Optional[Dict[str, Any]] = None
    # Minimum confidence score (0.0 - 1.0) for the step to be considered successful
    pass_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    # Whether the step should fail when the AI returns an error or unparseable response
    fail_on_error: bool = Field(default=True)
    # LLM temperature
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    # Maximum tokens for the AI response
    max_tokens: int = Field(default=1536, ge=100, le=8192)


class WaitConfig(BaseModel):
    duration_ms: int = Field(..., ge=0)
    condition: Optional[str] = None  # Optional polling condition


class ParallelConfig(BaseModel):
    branches: List[str] = Field(..., min_length=2)
    join_strategy: str = Field(default="all", pattern=r"^(all|any|first|custom)$")
    max_concurrency: int = Field(default=4, ge=1, le=16)


class SubflowConfig(BaseModel):
    workflow_name: str = Field(..., min_length=1)
    workflow_version: Optional[str] = None
    input_mapping: Dict[str, str] = Field(default_factory=dict)
    output_mapping: Dict[str, str] = Field(default_factory=dict)


class WorkflowStep(BaseModel):
    id: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")
    name: str = Field(..., min_length=1, max_length=255)
    type: WorkflowStepType
    description: Optional[str] = None
    enabled: bool = Field(default=True)
    # Config is type-specific
    config: Dict[str, Any] = Field(default_factory=dict)
    # Step-level retry policy (overrides workflow-level)
    retry_policy: Optional[RetryPolicy] = None
    # Next steps on success (list for branching)
    next_on_success: List[str] = Field(default_factory=list)
    # Next steps on failure
    next_on_failure: List[str] = Field(default_factory=list)
    # Timeout for this step in milliseconds
    timeout_ms: int = Field(default=60000, ge=1000)
    # Whether this step requires proof capture
    capture_proof: bool = Field(default=True)
    # Whether this step is a checkpoint (forces proof generation before continuing)
    checkpoint: bool = Field(default=False)
    # Whether this step can be skipped during remediation
    skippable: bool = Field(default=False)

    @field_validator("config")
    @classmethod
    def validate_config_type(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        step_type = info.data.get("type")
        if step_type == WorkflowStepType.http_request:
            HttpStepConfig.model_validate(v)
        elif step_type == WorkflowStepType.database_query:
            DatabaseQueryConfig.model_validate(v)
        elif step_type == WorkflowStepType.service_call:
            ServiceCallConfig.model_validate(v)
        elif step_type == WorkflowStepType.external_api:
            ExternalApiConfig.model_validate(v)
        elif step_type == WorkflowStepType.notification:
            NotificationConfig.model_validate(v)
        elif step_type == WorkflowStepType.dom_capture:
            DomCaptureConfig.model_validate(v)
        elif step_type == WorkflowStepType.decision_gate:
            DecisionGateConfig.model_validate(v)
        elif step_type == WorkflowStepType.ai_evaluation:
            AiEvaluationConfig.model_validate(v)
        elif step_type == WorkflowStepType.wait:
            WaitConfig.model_validate(v)
        elif step_type == WorkflowStepType.parallel:
            ParallelConfig.model_validate(v)
        elif step_type == WorkflowStepType.subflow:
            SubflowConfig.model_validate(v)
        return v


class WorkflowGraph(BaseModel):
    version: str = Field(default="1.0")
    description: Optional[str] = None
    # Entry point step ID
    entry_step: str = Field(..., min_length=1)
    # Global retry policy
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    # Circuit breaker configuration
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    # Steps in the workflow
    steps: List[WorkflowStep] = Field(..., min_length=1)
    # Global variables available to all steps
    variables: Dict[str, Any] = Field(default_factory=dict)
    # Whether to require human approval at decision gates by default
    human_gates_required: bool = Field(default=False)
    # Expected SLA in seconds
    sla_seconds: Optional[int] = Field(default=None, ge=1)

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: List[WorkflowStep]) -> List[WorkflowStep]:
        step_ids = {s.id for s in v}
        if len(step_ids) != len(v):
            raise ValueError("Workflow step IDs must be unique")
        return v

    @model_validator(mode="after")
    def validate_graph(self) -> "WorkflowGraph":
        step_ids = {s.id for s in self.steps}
        if self.entry_step not in step_ids:
            raise ValueError(f"Entry step '{self.entry_step}' not found in steps")
        for step in self.steps:
            for ref in step.next_on_success + step.next_on_failure:
                if ref not in step_ids and ref not in ("end", "fail"):
                    raise ValueError(
                        f"Step '{step.id}' references unknown step '{ref}'"
                    )
        return self


# ─── API Request/Response Schemas ─────────────────────────────────────────────

class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field(default="1.0.0", min_length=1, max_length=50)
    description: Optional[str] = None
    workflow_graph: WorkflowGraph
    sla_seconds: Optional[int] = Field(default=None, ge=1)
    human_gates_required: bool = Field(default=False)


class WorkflowUpdateRequest(BaseModel):
    description: Optional[str] = None
    active: Optional[bool] = None
    workflow_graph: Optional[WorkflowGraph] = None
    sla_seconds: Optional[int] = None
    human_gates_required: Optional[bool] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    version: str
    description: Optional[str]
    active: bool
    graph_hash: str
    workflow_graph: Dict[str, Any]
    sla_seconds: Optional[int]
    human_gates_required: bool
    created_at: str
    updated_at: str


class RunTriggerRequest(BaseModel):
    workflow_id: str
    project_id: Optional[str] = None
    trigger_event: str = Field(default="manual", min_length=1)
    input_data: Dict[str, Any] = Field(default_factory=dict)


class RunResponse(BaseModel):
    id: str
    workflow_id: str
    project_id: Optional[str]
    status: WorkflowRunStatus
    trigger_event: str
    confidence_score: Optional[float]
    merkle_root: Optional[str]
    radix_tx_ref: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str
    error_message: Optional[str]
    remediation_count: int
    human_intervened: bool
    awaiting_human_decision: bool


class StepExecutionResponse(BaseModel):
    id: str
    step_id: str
    step_index: int
    step_type: WorkflowStepType
    step_name: str
    status: StepExecutionStatus
    step_hash: Optional[str]
    duration_ms: Optional[int]
    retry_count: int
    error_message: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


class ProofResponse(BaseModel):
    id: str
    step_execution_id: Optional[str]
    proof_type: ProofType
    proof_hash: str
    merkle_leaf_index: Optional[int]
    captured_at: str


class TransitionResponse(BaseModel):
    id: str
    from_state: str
    to_state: str
    actor_type: str
    reason: Optional[str]
    transition_hash: str
    previous_hash: Optional[str]
    occurred_at: str


class RemediationResponse(BaseModel):
    id: str
    failure_condition: str
    action: RemediationAction
    status: RemediationStatus
    error_message: Optional[str]
    created_at: str
    resolved_at: Optional[str]


class EscalationResponse(BaseModel):
    id: str
    escalation_reason: str
    severity_score: float
    level: EscalationLevel
    status: EscalationStatus
    human_decision: Optional[str]
    human_notes: Optional[str]
    sla_deadline: Optional[str]
    acknowledged_at: Optional[str]
    resolved_at: Optional[str]
    created_at: str


class SyntheticActorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    actor_type: SyntheticActorType
    profile_key: str = Field(..., min_length=1, max_length=100)
    markers: Dict[str, Any] = Field(default_factory=dict)
    behavior_config: Dict[str, Any] = Field(default_factory=dict)
    context_data: Dict[str, Any] = Field(default_factory=dict)


class SyntheticActorResponse(BaseModel):
    id: str
    name: str
    actor_type: SyntheticActorType
    profile_key: str
    markers: Dict[str, Any]
    behavior_config: Dict[str, Any]
    context_data: Dict[str, Any]
    active: bool
    usage_count: int
    created_at: str
    last_used_at: Optional[str]


class HumanDecisionRequest(BaseModel):
    decision: str = Field(..., min_length=1, max_length=50)
    notes: Optional[str] = None


class ProofCertificateResponse(BaseModel):
    run_id: str
    workflow_name: str
    workflow_version: str
    merkle_root: str
    step_count: int
    proof_count: int
    started_at: str
    completed_at: Optional[str]
    radix_tx_ref: Optional[str]
    certificate_hash: str
    step_hashes: List[Dict[str, Any]]
