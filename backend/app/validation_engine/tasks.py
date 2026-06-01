"""Celery tasks for the Workflow Validation Engine."""

import uuid
from datetime import datetime, timezone, timedelta

from celery import shared_task
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.validation_engine.models import (
    EscalationLevel,
    EscalationStatus,
    HumanEscalation,
    ValidationRun,
    WorkflowRunStatus,
)
from app.validation_engine.orchestrator import ValidationOrchestrator
from app.validation_engine.proofs import ProofGenerator
from app.core.logging import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def execute_validation_run(self, run_id: str):
    """Execute a validation workflow run asynchronously.

    This task handles the full lifecycle of a run from RUNNING through
    to COMPLETED or FAILED, including proof generation and Radix anchoring.
    """
    import asyncio
    return asyncio.run(_execute_validation_run_async(run_id))


async def _execute_validation_run_async(run_id: str):
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(ValidationRun).where(ValidationRun.id == uuid.UUID(run_id))
            )
            run = result.scalar_one_or_none()
            if run is None:
                logger.error("validation_run_not_found", run_id=run_id)
                return {"error": "Run not found"}

            if run.status in (WorkflowRunStatus.completed, WorkflowRunStatus.failed, WorkflowRunStatus.archived):
                logger.warning("validation_run_already_terminal", run_id=run_id, status=run.status.value)
                return {"status": run.status.value, "message": "Run is already terminal"}

            orchestrator = ValidationOrchestrator(db)
            await orchestrator.execute_workflow(run_id)

            # Refresh run state
            await db.refresh(run)
            logger.info(
                "validation_run_completed",
                run_id=run_id,
                status=run.status.value,
                merkle_root=run.merkle_root,
                radix_tx_ref=run.radix_tx_ref,
            )
            return {
                "run_id": run_id,
                "status": run.status.value,
                "merkle_root": run.merkle_root,
                "radix_tx_ref": run.radix_tx_ref,
            }

        except Exception as exc:
            logger.error("validation_run_execution_error", run_id=run_id, error=str(exc))
            # Retry on transient failures
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc)
            raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def anchor_run_to_radix(self, run_id: str):
    """Anchor a validation run's Merkle root to the Radix ledger.

    This is a separate task to isolate ledger interaction failures
    from the main workflow execution.
    """
    import asyncio
    return asyncio.run(_anchor_run_async(run_id))


async def _anchor_run_async(run_id: str):
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(ValidationRun).where(ValidationRun.id == uuid.UUID(run_id))
            )
            run = result.scalar_one_or_none()
            if run is None:
                logger.error("anchor_run_not_found", run_id=run_id)
                return {"error": "Run not found"}

            generator = ProofGenerator()
            tx_ref = await generator.anchor_to_radix(db, run)

            if tx_ref:
                logger.info("radix_anchor_success", run_id=run_id, tx_ref=tx_ref)
                return {"run_id": run_id, "tx_ref": tx_ref}
            else:
                logger.warning("radix_anchor_failed", run_id=run_id)
                return {"run_id": run_id, "tx_ref": None, "warning": "Anchoring failed, will retry"}

        except Exception as exc:
            logger.error("radix_anchor_task_error", run_id=run_id, error=str(exc))
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc)
            raise


@shared_task
def cleanup_archived_runs(days: int = 30):
    """Archive old completed/failed runs and clean up proof data.

    Run daily via Celery beat.
    """
    import asyncio
    return asyncio.run(_cleanup_archived_async(days))


async def _cleanup_archived_async(days: int):
    async with AsyncSessionLocal() as db:
        from sqlalchemy import func
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(ValidationRun).where(
                ValidationRun.status.in_([WorkflowRunStatus.completed, WorkflowRunStatus.failed]),
                ValidationRun.completed_at < cutoff,
                ValidationRun.archived_at.is_(None),
            )
        )
        runs = result.scalars().all()

        archived_count = 0
        for run in runs:
            run.status = WorkflowRunStatus.archived
            run.archived_at = datetime.now(timezone.utc)
            archived_count += 1

        await db.commit()
        logger.info("cleanup_archived_runs", archived_count=archived_count, cutoff=cutoff.isoformat())
        return {"archived_count": archived_count}


@shared_task
def check_stalled_escalations():
    """Check for escalations that have exceeded their SLA and auto-escalate.

    Run every 15 minutes via Celery beat.
    """
    import asyncio
    return asyncio.run(_check_stalled_escalations_async())


async def _check_stalled_escalations_async():
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(HumanEscalation).where(
                HumanEscalation.status.in_([
                    EscalationStatus.pending,
                    EscalationStatus.acknowledged,
                ]),
                HumanEscalation.sla_deadline < now,
            )
        )
        escalations = result.scalars().all()

        escalated_count = 0
        for esc in escalations:
            # Auto-escalate to next level
            level_order = [
                EscalationLevel.l1_operator,
                EscalationLevel.l2_engineer,
                EscalationLevel.l3_architect,
                EscalationLevel.executive,
            ]
            current_idx = level_order.index(esc.level)
            if current_idx < len(level_order) - 1:
                new_level = level_order[current_idx + 1]
                esc.level = new_level
                esc.assigned_to = None  # Unassign so next level can pick it up
                # Extend SLA
                from datetime import timedelta
                esc.sla_deadline = now + timedelta(hours=4)
                logger.warning(
                    "escalation_auto_escalated",
                    escalation_id=str(esc.id),
                    old_level=esc.level.value,
                    new_level=new_level.value,
                )
                escalated_count += 1
            else:
                # Already at executive level — mark as timed out
                esc.status = EscalationStatus.timed_out
                logger.error("escalation_timed_out", escalation_id=str(esc.id))

        await db.commit()
        return {"escalated_count": escalated_count, "timed_out_count": len(escalations) - escalated_count}
