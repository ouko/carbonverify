"""
Audit trail API for CarbonVerify.

Provides endpoints for querying audit logs and verifying
blockchain-anchored entries on Radix DLT.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import AuditLog, AuditActionEnum, User
from app.auth.dependencies import require_admin, require_operator
from app.security.audit_logging import AuditLogger
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def list_audit_logs(
    target_type: Optional[str] = None,
    target_id: Optional[uuid.UUID] = None,
    actor_id: Optional[uuid.UUID] = None,
    action_type: Optional[AuditActionEnum] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """
    Query the audit trail with filters.
    Admin/operator only.
    """
    audit = AuditLogger(db)
    logs = await audit.get_audit_trail(
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        action_type=action_type,
        limit=limit,
        offset=offset,
    )

    return {
        "total": len(logs),
        "offset": offset,
        "limit": limit,
        "logs": [
            {
                "id": str(log.id),
                "action_type": log.action_type.value,
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "actor_type": log.actor_type,
                "target_type": log.target_type,
                "target_id": str(log.target_id) if log.target_id else None,
                "timestamp": log.timestamp,
                "input_hash": log.input_hash,
                "output_hash": log.output_hash,
                "radix_tx_ref": log.radix_tx_ref,
                "reasoning": log.reasoning,
                "ip_address": log.ip_address,
            }
            for log in logs
        ],
    }


@router.get("/logs/{log_id}")
async def get_audit_log(
    log_id: uuid.UUID,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Get a single audit log entry with full details."""
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return {
        "id": str(log.id),
        "action_type": log.action_type.value,
        "actor_id": str(log.actor_id) if log.actor_id else None,
        "actor_type": log.actor_type,
        "target_type": log.target_type,
        "target_id": str(log.target_id) if log.target_id else None,
        "timestamp": log.timestamp,
        "input_hash": log.input_hash,
        "output_hash": log.output_hash,
        "radix_tx_ref": log.radix_tx_ref,
        "reasoning": log.reasoning,
        "metadata": log.metadata_json,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
    }


@router.post("/logs/{log_id}/verify")
async def verify_audit_log(
    log_id: uuid.UUID,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the integrity of an audit log entry.

    Recomputes hashes and checks Radix DLT anchoring if applicable.
    """
    audit = AuditLogger(db)
    verification = await audit.verify_integrity(log_id)
    return verification


@router.get("/project/{project_id}")
async def get_project_audit_trail(
    project_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Get the complete audit trail for a project."""
    audit = AuditLogger(db)
    logs = await audit.get_audit_trail(
        target_id=project_id,
        limit=limit,
    )

    return {
        "project_id": str(project_id),
        "total_events": len(logs),
        "events": [
            {
                "id": str(log.id),
                "action": log.action_type.value,
                "actor": str(log.actor_id) if log.actor_id else "system",
                "timestamp": log.timestamp,
                "input_hash": log.input_hash,
                "output_hash": log.output_hash,
                "radix_tx_ref": log.radix_tx_ref,
                "anchored": log.radix_tx_ref is not None,
            }
            for log in logs
        ],
    }


@router.post("/anchor/{log_id}")
async def anchor_audit_log(
    log_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually anchor an existing audit log to Radix DLT.
    Admin only.
    """
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    if log.radix_tx_ref:
        return {"message": "Already anchored", "tx_ref": log.radix_tx_ref}

    audit = AuditLogger(db)
    anchor_data = {
        "action": log.action_type.value,
        "actor_id": str(log.actor_id) if log.actor_id else None,
        "target_id": str(log.target_id) if log.target_id else None,
        "input_hash": log.input_hash,
        "output_hash": log.output_hash,
        "timestamp": log.timestamp.isoformat(),
    }

    result = await audit.anchor.client.anchor_audit_log(anchor_data, memo=f"Manual:{log_id}")
    if result.success:
        log.radix_tx_ref = result.tx_ref
        await db.commit()
        logger.info("audit_log_manually_anchored", log_id=str(log_id), tx_ref=result.tx_ref)
        return {"message": "Anchored successfully", "tx_ref": result.tx_ref}
    else:
        raise HTTPException(status_code=500, detail=f"Anchoring failed: {result.error}")
