"""Agent decision audit trail API.

Exposes the immutable, Merkle-chained ``agent_decisions`` trail created by the
orchestrator. Mounted at ``/api/v1/audit`` alongside the legacy ``/audit``
router (audit logs + Radix anchoring).

Route ordering matters: static routes (``/decisions``, ``/verify-chain``)
are declared BEFORE the parameterized ``/{decision_id}`` route.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_viewer
from app.core.logging import get_logger
from app.database import get_db
from app.models import AgentDecision, User
from app.orchestrator.audit_chain import verify_chain
from app.schemas import AgentDecisionListResponse, AgentDecisionOut, VerifyChainResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/audit", tags=["audit-decisions"])


@router.get("/decisions", response_model=AgentDecisionListResponse)
async def list_agent_decisions(
    project_id: uuid.UUID | None = None,
    agent_type: str | None = None,
    action: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """List agent decisions with optional filters (newest first)."""
    filters = []
    if project_id:
        filters.append(AgentDecision.project_id == project_id)
    if agent_type:
        filters.append(AgentDecision.agent_type == agent_type)
    if action:
        filters.append(AgentDecision.action == action)

    total_result = await db.execute(
        select(func.count()).select_from(AgentDecision).where(*filters)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(AgentDecision)
        .where(*filters)
        .order_by(AgentDecision.created_at.desc(), AgentDecision.id.desc())
        .limit(limit)
        .offset(offset)
    )
    decisions = result.scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "decisions": decisions,
    }


@router.post("/verify-chain", response_model=VerifyChainResponse)
async def post_verify_chain(
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Verify the integrity of the agent decision Merkle chain."""
    result = await verify_chain(db)
    logger.info(
        "agent_decision_chain_verified",
        valid=result["valid"],
        checked=result["checked"],
        first_broken_id=str(result["first_broken_id"]) if result["first_broken_id"] else None,
    )
    return result


@router.get("/{decision_id}", response_model=AgentDecisionOut)
async def get_agent_decision(
    decision_id: uuid.UUID,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Get a single agent decision by its public decision_id."""
    result = await db.execute(
        select(AgentDecision).where(AgentDecision.decision_id == decision_id)
    )
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Agent decision not found")
    return decision
