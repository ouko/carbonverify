"""REST API for the human escalation & notification service (Command Center)."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_operator
from app.database import get_db
from app.escalations.models import EscalationEvent, EscalationStatus
from app.escalations.service import EscalationService
from app.models import AgentDecision, HumanReviewQueue, QueueStatusEnum, User

router = APIRouter(prefix="/api/v1/escalations", tags=["escalations"])

CONFIDENCE_WINDOW = timedelta(hours=24)
REMEDIATION_WINDOW = timedelta(days=7)
VALIDATION_WINDOW = timedelta(days=7)


def _event_to_dict(event: EscalationEvent) -> Dict[str, Any]:
    return {
        "id": str(event.id),
        "project_id": str(event.project_id) if event.project_id else None,
        "source": event.source,
        "title": event.title,
        "detail": event.detail,
        "context_package": event.context_package or {},
        "priority": event.priority,
        "severity_score": event.severity_score,
        "status": event.status.value,
        "channels_sent": event.channels_sent or {},
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "acknowledged_at": event.acknowledged_at.isoformat() if event.acknowledged_at else None,
        "acknowledged_by": str(event.acknowledged_by) if event.acknowledged_by else None,
        "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
        "resolved_by": str(event.resolved_by) if event.resolved_by else None,
        "resolution_notes": event.resolution_notes,
    }


@router.get("/")
async def list_escalations(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[int] = Query(None, ge=0, le=2),
    project_id: Optional[uuid.UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
) -> Dict[str, Any]:
    stmt = select(EscalationEvent)
    count_stmt = select(func.count(EscalationEvent.id))
    if status_filter:
        try:
            parsed_status = EscalationStatus(status_filter)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status_filter}")
        stmt = stmt.where(EscalationEvent.status == parsed_status)
        count_stmt = count_stmt.where(EscalationEvent.status == parsed_status)
    if priority is not None:
        stmt = stmt.where(EscalationEvent.priority == priority)
        count_stmt = count_stmt.where(EscalationEvent.priority == priority)
    if project_id is not None:
        stmt = stmt.where(EscalationEvent.project_id == project_id)
        count_stmt = count_stmt.where(EscalationEvent.project_id == project_id)

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.order_by(EscalationEvent.created_at.desc()).offset(skip).limit(limit)
    )
    items = [_event_to_dict(e) for e in result.scalars().all()]
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/stats")
async def escalation_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
) -> Dict[str, Any]:
    result = await db.execute(select(EscalationEvent))
    events = result.scalars().all()

    by_status: Dict[str, int] = {s.value: 0 for s in EscalationStatus}
    by_priority: Dict[str, int] = {"0": 0, "1": 0, "2": 0}
    ack_seconds: List[float] = []
    for event in events:
        by_status[event.status.value] += 1
        by_priority[str(event.priority)] = by_priority.get(str(event.priority), 0) + 1
        if event.acknowledged_at and event.created_at:
            created = event.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            acknowledged = event.acknowledged_at
            if acknowledged.tzinfo is None:
                acknowledged = acknowledged.replace(tzinfo=timezone.utc)
            ack_seconds.append((acknowledged - created).total_seconds())

    return {
        "total": len(events),
        "by_status": by_status,
        "by_priority": by_priority,
        "open_p0": sum(1 for e in events if e.priority == 0 and e.status == EscalationStatus.open),
        "avg_time_to_ack_seconds": (sum(ack_seconds) / len(ack_seconds)) if ack_seconds else None,
    }


@router.get("/health/score")
async def health_score(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
) -> Dict[str, Any]:
    """Composite 0-100 system health score with per-component breakdown."""
    now = datetime.now(timezone.utc)
    components: Dict[str, Any] = {}

    # 1. Agent confidence (last 24h of orchestration decisions).
    cutoff = now - CONFIDENCE_WINDOW
    avg_conf = (
        await db.execute(
            select(func.avg(AgentDecision.confidence_score)).where(
                AgentDecision.created_at >= cutoff,
                AgentDecision.confidence_score.isnot(None),
            )
        )
    ).scalar()
    if avg_conf is not None:
        components["agent_confidence"] = round(float(avg_conf) * 100, 1)

    # 2. Open escalations, weighted by priority.
    open_result = await db.execute(
        select(EscalationEvent).where(EscalationEvent.status == EscalationStatus.open)
    )
    open_events = open_result.scalars().all()
    p0 = sum(1 for e in open_events if e.priority == 0)
    p1 = sum(1 for e in open_events if e.priority == 1)
    p2 = sum(1 for e in open_events if e.priority == 2)
    weighted = p0 * 25 + p1 * 10 + p2 * 2
    components["open_escalations"] = {
        "score": max(0.0, round(100 - weighted, 1)),
        "open_p0": p0,
        "open_p1": p1,
        "open_p2": p2,
    }

    # 3. Review queue depth (pending + in_review).
    depth = (
        await db.execute(
            select(func.count(HumanReviewQueue.id)).where(
                HumanReviewQueue.status.in_([QueueStatusEnum.pending, QueueStatusEnum.in_review])
            )
        )
    ).scalar() or 0
    components["review_queue_depth"] = {
        "score": max(0.0, round(100 - int(depth) * 5, 1)),
        "pending": int(depth),
    }

    # 4. Remediation resolution rate (validation engine), last 7 days.
    try:
        from app.validation_engine.models import (
            RemediationStatus,
            ValidationRemediation,
        )

        rem_cutoff = now - REMEDIATION_WINDOW
        rem_result = await db.execute(
            select(ValidationRemediation.status, func.count()).where(
                ValidationRemediation.created_at >= rem_cutoff
            ).group_by(ValidationRemediation.status)
        )
        counts = {row[0]: row[1] for row in rem_result.all()}
        resolved = counts.get(RemediationStatus.succeeded, 0)
        unresolved = counts.get(RemediationStatus.attempted, 0) + counts.get(RemediationStatus.failed, 0)
        if resolved + unresolved > 0:
            rate = resolved / (resolved + unresolved)
            components["remediation_resolution_rate"] = {
                "score": round(rate * 100, 1),
                "resolved": resolved,
                "unresolved": unresolved,
            }
    except ImportError:  # pragma: no cover — validation engine always present here
        pass

    # 5. Recent validation run health, last 7 days.
    try:
        from app.validation_engine.models import ValidationRun, WorkflowRunStatus

        val_cutoff = now - VALIDATION_WINDOW
        val_result = await db.execute(
            select(ValidationRun.status, func.count()).where(
                ValidationRun.created_at >= val_cutoff
            ).group_by(ValidationRun.status)
        )
        val_counts = {row[0]: row[1] for row in val_result.all()}
        completed = val_counts.get(WorkflowRunStatus.completed, 0)
        failed = val_counts.get(WorkflowRunStatus.failed, 0)
        if completed + failed > 0:
            components["validation_health"] = {
                "score": round(completed / (completed + failed) * 100, 1),
                "completed": completed,
                "failed": failed,
            }
    except ImportError:  # pragma: no cover
        pass

    weights = {
        "agent_confidence": 0.30,
        "open_escalations": 0.30,
        "review_queue_depth": 0.20,
        "remediation_resolution_rate": 0.10,
        "validation_health": 0.10,
    }
    available = [
        (weights[name], comp["score"] if isinstance(comp, dict) else comp)
        for name, comp in components.items()
        if name in weights
    ]
    if available:
        total_weight = sum(w for w, _ in available)
        score = sum(w * s for w, s in available) / total_weight
    else:
        score = 100.0

    return {"score": int(round(max(0.0, min(100.0, score)))), "components": components}


@router.get("/{event_id}")
async def get_escalation(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
) -> Dict[str, Any]:
    event = await EscalationService(db).get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return _event_to_dict(event)


@router.post("/{event_id}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_escalation(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> Dict[str, Any]:
    try:
        event = await EscalationService(db).acknowledge(event_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _event_to_dict(event)


class ResolvePayload(BaseModel):
    notes: str = ""


@router.post("/{event_id}/resolve", status_code=status.HTTP_200_OK)
async def resolve_escalation(
    event_id: uuid.UUID,
    payload: ResolvePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> Dict[str, Any]:
    try:
        event = await EscalationService(db).resolve(event_id, current_user.id, payload.notes)
    except ValueError as exc:
        detail = str(exc)
        code = 409 if "already" in detail else 404
        raise HTTPException(status_code=code, detail=detail)
    return _event_to_dict(event)
