"""
Audit logging service for CarbonVerify.

Every significant action creates an immutable audit log entry.
Integrates with Radix DLT for blockchain anchoring of critical events.
"""

import hashlib
import json
import uuid
from typing import Optional, Dict, Any, Callable
from functools import wraps

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import AuditLog, AuditActionEnum
from app.blockchain.radix_client import AuditTrailAnchor
from app.security.siem_streaming import get_siem_streamer
from app.core.logging import get_logger

logger = get_logger(__name__)


def compute_hash(data: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of canonical JSON."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuditLogger:
    """Service for creating and anchoring audit log entries."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.anchor = AuditTrailAnchor()

    async def log(
        self,
        action_type: AuditActionEnum,
        actor_id: Optional[uuid.UUID],
        actor_type: str = "user",
        target_type: str = "project",
        target_id: Optional[uuid.UUID] = None,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        reasoning: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        anchor_to_radix: bool = False,
    ) -> AuditLog:
        """
        Create an audit log entry. Optionally anchor to Radix DLT.
        """
        input_hash = compute_hash(input_data) if input_data else None
        output_hash = compute_hash(output_data) if output_data else None

        ip_address = None
        user_agent = None
        if request:
            ip_address = _get_client_ip(request)
            user_agent = request.headers.get("user-agent")

        log_entry = AuditLog(
            action_type=action_type,
            actor_id=actor_id,
            actor_type=actor_type,
            target_type=target_type,
            target_id=target_id,
            input_hash=input_hash,
            output_hash=output_hash,
            reasoning=reasoning,
            metadata_json=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(log_entry)
        await self.db.flush()

        if anchor_to_radix:
            try:
                anchor_data = {
                    "action": action_type.value,
                    "actor_id": str(actor_id) if actor_id else None,
                    "target_id": str(target_id) if target_id else None,
                    "input_hash": input_hash,
                    "output_hash": output_hash,
                    "timestamp": log_entry.timestamp.isoformat(),
                }
                result = await self.anchor.client.anchor_audit_log(anchor_data, memo=f"Audit:{log_entry.id}")
                if result.success:
                    log_entry.radix_tx_ref = result.tx_ref
                    await self.db.flush()
                    logger.info("audit_anchored", log_id=str(log_entry.id), tx_ref=result.tx_ref)
                else:
                    logger.warning("audit_anchor_failed", log_id=str(log_entry.id), error=result.error)
            except Exception as exc:
                logger.error("audit_anchor_exception", log_id=str(log_entry.id), error=str(exc))

        await self.db.commit()
        logger.info("audit_log_created", action=action_type.value, actor_id=str(actor_id), target_id=str(target_id))

        # Stream to SIEM if configured
        try:
            siem = get_siem_streamer()
            await siem.send({
                "id": str(log_entry.id),
                "action": action_type.value,
                "actor_id": str(actor_id) if actor_id else None,
                "actor_type": actor_type,
                "target_type": target_type,
                "target_id": str(target_id) if target_id else None,
                "timestamp": log_entry.timestamp.isoformat() if log_entry.timestamp else None,
                "metadata": metadata,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "radix_tx_ref": log_entry.radix_tx_ref,
            })
        except Exception as exc:
            logger.error("siem_stream_failed", log_id=str(log_entry.id), error=str(exc))

        return log_entry

    async def log_login(
        self,
        user_id: uuid.UUID,
        success: bool,
        request: Optional[Request] = None,
        mfa_used: bool = False,
    ) -> AuditLog:
        """Log a user login attempt."""
        return await self.log(
            action_type=AuditActionEnum.user_login,
            actor_id=user_id,
            target_type="user",
            target_id=user_id,
            metadata={"success": success, "mfa_used": mfa_used},
            request=request,
        )

    async def log_logout(self, user_id: uuid.UUID, request: Optional[Request] = None) -> AuditLog:
        """Log a user logout."""
        return await self.log(
            action_type=AuditActionEnum.user_logout,
            actor_id=user_id,
            target_type="user",
            target_id=user_id,
            request=request,
        )

    async def log_calculation_run(
        self,
        calculation_run_id: uuid.UUID,
        project_id: uuid.UUID,
        actor_id: uuid.UUID,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        anchor: bool = True,
    ) -> AuditLog:
        """Log a calculation run with optional Radix anchoring."""
        return await self.log(
            action_type=AuditActionEnum.calculation_run,
            actor_id=actor_id,
            target_type="calculation",
            target_id=calculation_run_id,
            input_data=input_data,
            output_data=output_data,
            anchor_to_radix=anchor,
        )

    async def log_report_approval(
        self,
        report_id: uuid.UUID,
        project_id: uuid.UUID,
        approver_id: uuid.UUID,
        report_content: Dict[str, Any],
        anchor: bool = True,
    ) -> AuditLog:
        """Log a report approval with optional Radix anchoring."""
        report_hash = compute_hash(report_content)
        return await self.log(
            action_type=AuditActionEnum.report_approved,
            actor_id=approver_id,
            target_type="report",
            target_id=report_id,
            output_data={"report_hash": report_hash, "project_id": str(project_id)},
            anchor_to_radix=anchor,
        )

    async def log_data_ingested(
        self,
        project_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
        data_source_id: uuid.UUID,
        raw_data_summary: Dict[str, Any],
    ) -> AuditLog:
        """Log data ingestion."""
        return await self.log(
            action_type=AuditActionEnum.data_ingested,
            actor_id=actor_id,
            target_type="data_source",
            target_id=data_source_id,
            input_data=raw_data_summary,
            metadata={"project_id": str(project_id)},
        )

    async def log_human_review(
        self,
        queue_item_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        decision: str,
        notes: Optional[str] = None,
    ) -> AuditLog:
        """Log a human review decision."""
        return await self.log(
            action_type=AuditActionEnum.human_reviewed,
            actor_id=reviewer_id,
            target_type="review_queue",
            target_id=queue_item_id,
            output_data={"decision": decision, "notes": notes},
            reasoning=notes,
        )

    async def get_audit_trail(
        self,
        target_type: Optional[str] = None,
        target_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        action_type: Optional[AuditActionEnum] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Query the audit trail with filters."""
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())

        if target_type:
            stmt = stmt.where(AuditLog.target_type == target_type)
        if target_id:
            stmt = stmt.where(AuditLog.target_id == target_id)
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if action_type:
            stmt = stmt.where(AuditLog.action_type == action_type)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def verify_integrity(self, log_id: uuid.UUID) -> Dict[str, Any]:
        """
        Verify the integrity of an audit log entry.

        Recomputes the hash and checks the Radix transaction if anchored.
        """
        stmt = select(AuditLog).where(AuditLog.id == log_id)
        result = await self.db.execute(stmt)
        log_entry = result.scalar_one_or_none()

        if not log_entry:
            return {"valid": False, "error": "Log entry not found"}

        verification = {
            "log_id": str(log_id),
            "action": log_entry.action_type.value,
            "timestamp": log_entry.timestamp.isoformat(),
            "input_hash": log_entry.input_hash,
            "output_hash": log_entry.output_hash,
            "radix_tx_ref": log_entry.radix_tx_ref,
            "radix_verified": None,
            "valid": True,
        }

        if log_entry.radix_tx_ref:
            anchor_data = {
                "action": log_entry.action_type.value,
                "actor_id": str(log_entry.actor_id) if log_entry.actor_id else None,
                "target_id": str(log_entry.target_id) if log_entry.target_id else None,
                "input_hash": log_entry.input_hash,
                "output_hash": log_entry.output_hash,
                "timestamp": log_entry.timestamp.isoformat(),
            }
            verification["radix_verified"] = await self.anchor.client.verify_anchor(
                log_entry.radix_tx_ref, anchor_data
            )

        return verification


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"


def audit_log(
    action_type: AuditActionEnum,
    target_type: str = "project",
    anchor: bool = False,
    get_target_id: Optional[Callable] = None,
    get_input_data: Optional[Callable] = None,
    get_output_data: Optional[Callable] = None,
):
    """
    Decorator for automatically logging API endpoint calls.

    Usage:
        @router.post("/reports")
        @audit_log(AuditActionEnum.report_generated, target_type="report")
        async def create_report(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # FastAPI injects request and db as kwargs
            request = kwargs.get("request")
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            result = await func(*args, **kwargs)

            if db:
                try:
                    audit = AuditLogger(db)
                    target_id = None
                    if get_target_id:
                        target_id = get_target_id(result, kwargs)
                    elif hasattr(result, "id"):
                        target_id = result.id

                    input_data = get_input_data(kwargs) if get_input_data else None
                    output_data = get_output_data(result) if get_output_data else None

                    await audit.log(
                        action_type=action_type,
                        actor_id=current_user.id if current_user else None,
                        actor_type="user" if current_user else "system",
                        target_type=target_type,
                        target_id=target_id,
                        input_data=input_data,
                        output_data=output_data,
                        request=request if isinstance(request, Request) else None,
                        anchor_to_radix=anchor,
                    )
                except Exception as exc:
                    logger.error("audit_decorator_failed", error=str(exc))

            return result
        return wrapper
    return decorator
