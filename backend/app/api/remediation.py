"""Shared self-healing remediation engine API.

Route ordering matters: static routes (``/rules``, ``/attempts``, ``/stats``)
are declared BEFORE the parameterized ``/attempts/{attempt_id}/retry`` route.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_operator, require_viewer
from app.core.logging import get_logger
from app.database import get_db
from app.models import User
from app.remediation.engine import RemediationEngine, hash_state
from app.remediation.models import RemediationAttempt, RemediationRule

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/remediation", tags=["remediation"])


def _rule_out(rule: RemediationRule) -> dict[str, Any]:
    return {
        "id": str(rule.id),
        "rule_key": rule.rule_key,
        "category": rule.category,
        "description": rule.description,
        "strategy": rule.strategy,
        "config": rule.config,
        "enabled": rule.enabled,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


def _attempt_out(row: RemediationAttempt) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "rule_key": row.rule_key,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "project_id": str(row.project_id) if row.project_id else None,
        "status": row.status,
        "attempt_number": row.attempt_number,
        "before_state_hash": row.before_state_hash,
        "after_state_hash": row.after_state_hash,
        "detail": row.detail,
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/rules")
async def list_rules(
    enabled: bool | None = None,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List remediation rules (optionally filtered by enabled flag)."""
    stmt = select(RemediationRule).order_by(RemediationRule.rule_key)
    if enabled is not None:
        stmt = stmt.where(RemediationRule.enabled.is_(enabled))
    result = await db.execute(stmt)
    return {"rules": [_rule_out(rule) for rule in result.scalars().all()]}


@router.get("/attempts")
async def list_attempts(
    rule_key: str | None = None,
    target_type: str | None = None,
    status: str | None = None,
    project_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List remediation attempts with filters (newest first, paginated)."""
    filters = []
    if rule_key:
        filters.append(RemediationAttempt.rule_key == rule_key)
    if target_type:
        filters.append(RemediationAttempt.target_type == target_type)
    if status:
        filters.append(RemediationAttempt.status == status)
    if project_id:
        filters.append(RemediationAttempt.project_id == project_id)

    total_result = await db.execute(
        select(func.count()).select_from(RemediationAttempt).where(*filters)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(RemediationAttempt)
        .where(*filters)
        .order_by(RemediationAttempt.created_at.desc(), RemediationAttempt.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "attempts": [_attempt_out(row) for row in result.scalars().all()],
    }


@router.get("/stats")
async def remediation_stats(
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Aggregate remediation statistics, including resolution rate."""
    engine = RemediationEngine(db)
    return await engine.stats()


@router.post("/attempts/{attempt_id}/retry")
async def retry_attempt(
    attempt_id: uuid.UUID,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Manually re-run a previous remediation attempt with a fresh budget."""
    result = await db.execute(
        select(RemediationAttempt).where(RemediationAttempt.id == attempt_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Remediation attempt not found")

    failing_state = (row.detail or {}).get("failing_state")
    if not isinstance(failing_state, dict):
        raise HTTPException(
            status_code=422,
            detail="Attempt has no failing_state snapshot to re-run from",
        )

    engine = RemediationEngine(db)
    outcome = await engine.remediate(
        row.rule_key,
        row.target_type,
        row.target_id,
        failing_state,
        project_id=row.project_id,
        attempts_so_far=0,
    )
    logger.info(
        "remediation_manual_retry",
        attempt_id=str(attempt_id),
        operator_id=str(current_user.id),
        status=outcome.status,
    )
    return {
        "status": outcome.status,
        "attempts_used": outcome.attempts_used,
        "detail": outcome.detail,
        "before_state_hash": outcome.before_hash or hash_state(failing_state),
        "after_state_hash": outcome.after_hash,
        "rule_key": outcome.rule_key,
    }
