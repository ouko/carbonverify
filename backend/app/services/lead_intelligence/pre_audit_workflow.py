"""Default pre-audit validation workflow template."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.validation_engine.models import ValidationWorkflow
from app.validation_engine.schemas import WorkflowGraph

logger = get_logger(__name__)

PRE_AUDIT_WORKFLOW_NAME = "pre_audit_document_package"
PRE_AUDIT_WORKFLOW_VERSION = "1.0.0"


def build_pre_audit_graph() -> WorkflowGraph:
    return WorkflowGraph(
        version="1.0",
        description="Pre-audit registry-imported project documents for completeness and consistency.",
        entry_step="document_presence_gate",
        variables={},
        steps=[
            {
                "id": "document_presence_gate",
                "name": "Required Documents Present",
                "type": "database_query",
                "config": {
                    "query": "SELECT document_type FROM data_sources WHERE project_id = :project_id AND source_type = 'document'",
                    "params": {"project_id": "${project_id}"},
                    "snapshot_result": True,
                },
                "next_on_success": ["ai_evaluation"],
                "next_on_failure": ["gap_notification"],
            },
            {
                "id": "ai_evaluation",
                "name": "AI Pre-Audit Evaluation",
                "type": "ai_evaluation",
                "config": {
                    "prompt": (
                        "You are a carbon credit verification pre-auditor. "
                        "Review the project metadata and document excerpts below. "
                        "Evaluate against standard VCS/Gold Standard/CDM requirements for: "
                        "completeness of baseline scenario and additionality demonstration, "
                        "clarity of monitoring plan, consistency across documents, "
                        "presence of stakeholder consultation evidence, and methodology-specific requirements. "
                        "Return strict JSON with keys: score (float 0.0-1.0), passed (bool), "
                        "reasoning (string including a short gap list and risk flags), recommendation (string)."
                    ),
                    "input_data": {
                        "project_name": "${project_name}",
                        "methodology": "${methodology}",
                        "document_excerpts": "${document_excerpts}",
                    },
                    "pass_threshold": 0.7,
                    "temperature": 0.2,
                    "max_tokens": 2048,
                    "fail_on_error": False,
                },
                "next_on_success": ["readiness_decision_gate"],
                "next_on_failure": ["gap_notification"],
            },
            {
                "id": "readiness_decision_gate",
                "name": "Readiness Decision Gate",
                "type": "decision_gate",
                "config": {
                    "condition_expression": "${ai_evaluation.passed} == True",
                    "require_human_approval": False,
                    "auto_approve_threshold": 0.95,
                    "escalation_level": "l1_operator",
                },
                "next_on_success": ["end"],
                "next_on_failure": ["gap_notification"],
            },
            {
                "id": "gap_notification",
                "name": "Notify Operator of Gaps",
                "type": "notification",
                "config": {
                    "channel": "in_app",
                    "recipients": [],
                    "subject": "Pre-audit gaps detected",
                    "body": "Pre-audit completed with gaps. Review the project detail page.",
                },
                "next_on_success": ["end"],
                "next_on_failure": ["end"],
            },
        ],
    )


async def get_or_create_pre_audit_workflow(db: AsyncSession) -> ValidationWorkflow:
    """Return the active pre-audit workflow, creating it if missing."""
    result = await db.execute(
        select(ValidationWorkflow)
        .where(ValidationWorkflow.name == PRE_AUDIT_WORKFLOW_NAME)
        .where(ValidationWorkflow.active == True)
        .order_by(ValidationWorkflow.version.desc())
        .limit(1)
    )
    workflow = result.scalar_one_or_none()
    if workflow is not None:
        return workflow

    graph = build_pre_audit_graph()
    import hashlib, json
    graph_hash = hashlib.sha256(
        json.dumps(graph.model_dump(), sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()

    workflow = ValidationWorkflow(
        name=PRE_AUDIT_WORKFLOW_NAME,
        version=PRE_AUDIT_WORKFLOW_VERSION,
        description="Default pre-audit workflow for registry-imported projects",
        workflow_graph=graph.model_dump(),
        graph_hash=graph_hash,
        active=True,
        human_gates_required=False,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    logger.info("pre_audit_workflow_created", workflow_id=str(workflow.id))
    return workflow
