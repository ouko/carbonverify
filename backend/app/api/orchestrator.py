"""API endpoints for Kimi Claw multi-agent orchestration."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import (
    AgentRun,
    HumanReviewQueue,
    Project,
    QueueStatusEnum,
    User,
)
from app.auth.dependencies import require_operator, require_viewer
from app.orchestrator.orchestrator import KimiClawOrchestrator
from app.orchestrator.events import EventLogger
from app.services.kimi_api import get_kimi_client
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


# ─── Orchestrator Control ─────────────────────────────────────────────────────

class ProjectTriggerRequest(BaseModel):
    trigger: str
    context: Optional[Dict[str, Any]] = None


@router.post("/projects/{project_id}/trigger")
async def trigger_project_state(
    project_id: uuid.UUID,
    payload: ProjectTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Trigger a state transition for a project."""
    result = await db.execute(select(Project).where(Project.id == payload.project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    orchestrator = KimiClawOrchestrator(db)
    result = await orchestrator.process_project(project_id, payload.trigger, payload.context or {})

    logger.info(
        "orchestrator_triggered",
        project_id=str(project_id),
        trigger=payload.trigger,
        user_id=str(current_user.id),
    )
    return result


@router.get("/projects/{project_id}/state")
async def get_project_orchestrator_state(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Get full orchestrator state for a project."""
    orchestrator = KimiClawOrchestrator(db)
    return await orchestrator.get_project_state(project_id)


@router.get("/projects/{project_id}/events")
async def get_project_event_history(
    project_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Get orchestrator event history for a project."""
    event_logger = EventLogger(db)
    events = await event_logger.get_event_history(project_id, limit=limit)
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type.value,
            "from_state": e.from_state,
            "to_state": e.to_state,
            "agent_run_id": str(e.agent_run_id) if e.agent_run_id else None,
            "confidence_score": e.confidence_score,
            "details": e.details,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.get("/projects/{project_id}/agent-runs")
async def list_agent_runs(
    project_id: uuid.UUID,
    agent_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """List agent execution runs for a project."""
    stmt = select(AgentRun).where(AgentRun.project_id == project_id)
    if agent_type:
        stmt = stmt.where(AgentRun.agent_type == agent_type)
    if status:
        stmt = stmt.where(AgentRun.status == status)
    stmt = stmt.order_by(AgentRun.created_at.desc())

    result = await db.execute(stmt)
    runs = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "agent_type": r.agent_type.value,
            "status": r.status.value,
            "trigger_event": r.trigger_event,
            "confidence_score": r.confidence_score,
            "execution_time_ms": r.execution_time_ms,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]


# ─── Human Review Queue ───────────────────────────────────────────────────────

@router.get("/review-queue", response_model=List[Dict[str, Any]])
async def list_orchestrator_review_queue(
    status: Optional[str] = None,
    assigned_to: Optional[uuid.UUID] = None,
    min_priority: int = Query(1, ge=1, le=5),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """List human review queue items with orchestrator context."""
    stmt = select(HumanReviewQueue).where(HumanReviewQueue.priority >= min_priority)
    if status:
        stmt = stmt.where(HumanReviewQueue.status == status)
    if assigned_to:
        stmt = stmt.where(HumanReviewQueue.assigned_to == assigned_to)
    stmt = stmt.order_by(HumanReviewQueue.priority_score.desc().nullslast(), HumanReviewQueue.created_at.asc()).offset(skip).limit(limit)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return [
        {
            "id": str(item.id),
            "item_type": item.item_type.value,
            "item_id": str(item.item_id),
            "reason": item.reason,
            "priority": item.priority,
            "priority_score": item.priority_score,
            "sla_deadline": item.sla_deadline.isoformat() if item.sla_deadline else None,
            "sla_remaining_hours": (
                round((item.sla_deadline - datetime.now(timezone.utc)).total_seconds() / 3600, 1)
                if item.sla_deadline else None
            ),
            "assigned_to": str(item.assigned_to) if item.assigned_to else None,
            "status": item.status.value,
            "suggested_action": item.suggested_action,
            "confidence_gap": item.confidence_gap,
            "context": item.context_json,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]


class ReviewResolutionRequest(BaseModel):
    decision: str  # approve | reject | escalate
    resolution_notes: str


@router.post("/review-queue/{item_id}/resolve")
async def resolve_review_item(
    item_id: uuid.UUID,
    payload: ReviewResolutionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Resolve a human review queue item."""
    if payload.decision not in ("approve", "reject", "escalate"):
        raise HTTPException(status_code=400, detail="Decision must be 'approve', 'reject', or 'escalate'")

    orchestrator = KimiClawOrchestrator(db)
    result = await orchestrator.resolve_human_review(
        queue_item_id=item_id,
        decision=payload.decision,
        resolution_notes=payload.resolution_notes,
        user_id=current_user.id,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    logger.info(
        "review_item_resolved",
        item_id=str(item_id),
        decision=payload.decision,
        user_id=str(current_user.id),
    )
    return result


@router.post("/review-queue/{item_id}/assign")
async def assign_review_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Self-assign a review queue item."""
    result = await db.execute(select(HumanReviewQueue).where(HumanReviewQueue.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    item.assigned_to = current_user.id
    item.status = QueueStatusEnum.in_review
    await db.commit()
    await db.refresh(item)

    return {
        "id": str(item.id),
        "assigned_to": str(item.assigned_to),
        "status": item.status.value,
    }


# ─── Kimi AI Integration ──────────────────────────────────────────────────────

class DraftVVBResponseRequest(BaseModel):
    query_text: str
    project_id: uuid.UUID


@router.post("/ai/draft-vvb-response")
async def draft_vvb_response(
    payload: DraftVVBResponseRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Use Kimi AI to draft a VVB clarification response."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    client = get_kimi_client()
    project_data = {
        "name": project.name,
        "methodology": project.methodology.value,
        "status": project.status.value,
    }

    content = await client.draft_vvb_response(
        query_text=payload.query_text,
        project_data=project_data,
    )
    return {"draft": content, "project_id": str(payload.project_id)}


@router.post("/ai/executive-summary")
async def generate_executive_summary(
    project_id: uuid.UUID,
    calculation_run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Generate an executive summary using Kimi AI."""
    from app.models import CalculationRun

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    calc_result = await db.execute(select(CalculationRun).where(CalculationRun.id == calculation_run_id))
    calc = calc_result.scalar_one_or_none()
    if not calc:
        raise HTTPException(status_code=404, detail="Calculation run not found")

    client = get_kimi_client()
    project_data = {
        "name": project.name,
        "methodology": project.methodology.value,
        "monitoring_period": f"{calc.monitoring_period_start} to {calc.monitoring_period_end}",
    }
    calculation_results = {
        "emissions_reduction_tco2e": calc.emissions_reduction_tCO2e,
        "fnrb": calc.fNRB_value,
        "uncertainty_95ci": calc.uncertainty_95CI,
        "methodology_compliance_score": calc.methodology_compliance_score,
        "leakage_tco2e": calc.leakage_assessment.get("total_leakage_tco2e") if calc.leakage_assessment else None,
    }

    content = await client.generate_executive_summary(
        project_data=project_data,
        calculation_results=calculation_results,
    )
    return {"summary": content, "project_id": str(project_id), "calculation_run_id": str(calculation_run_id)}


class MethodologyQARequest(BaseModel):
    question: str
    methodology: str
    context_documents: Optional[List[str]] = None


@router.post("/ai/methodology-qa")
async def methodology_qa(
    payload: MethodologyQARequest,
    _: User = Depends(require_viewer),
):
    """Ask a methodology question using Kimi AI RAG."""
    client = get_kimi_client()
    answer = await client.answer_methodology_question(
        question=payload.question,
        methodology=payload.methodology,
        context_documents=payload.context_documents,
    )
    return {"question": payload.question, "methodology": payload.methodology, "answer": answer}


class ExplainAnomalyRequest(BaseModel):
    data_point: Dict[str, Any]
    field_name: str = "value"
    historical_context: Optional[List[Dict[str, Any]]] = None


@router.post("/ai/explain-anomaly")
async def explain_anomaly(
    payload: ExplainAnomalyRequest,
    _: User = Depends(require_operator),
):
    """Get a natural language explanation of an anomalous data point."""
    client = get_kimi_client()
    explanation = await client.explain_anomaly(
        data_point=payload.data_point,
        field_name=payload.field_name,
        historical_context=payload.historical_context,
    )
    return {"explanation": explanation, "data_point": payload.data_point}


# ─── Agent Direct Invocation ──────────────────────────────────────────────────

@router.post("/projects/{project_id}/agents/{agent_type}/run")
async def run_agent_directly(
    project_id: uuid.UUID,
    agent_type: str,
    context: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Manually trigger an agent run for a project."""
    from app.agents import AGENT_REGISTRY

    if agent_type not in AGENT_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {agent_type}")

    orchestrator = KimiClawOrchestrator(db)
    result = await orchestrator.dispatch_agent(
        project_id=project_id,
        agent_type=agent_type,
        trigger_event="manual",
        context=context or {},
    )

    logger.info(
        "agent_run_manual",
        project_id=str(project_id),
        agent_type=agent_type,
        user_id=str(current_user.id),
    )
    return result.to_dict()
