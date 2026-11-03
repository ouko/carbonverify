"""Celery jobs for continuous synthetic validation and health snapshots.

- ``run_synthetic_validation`` (15-minute beat): queues one validation run per
  synthetic journey template, tagged with a synthetic actor marker, then
  appends a health snapshot. Bounded: a journey whose previous synthetic run
  is still PENDING/QUEUED/RUNNING is skipped.

DB access goes through ``app.database.get_db_context`` (lazy import at call
time) so tests can route sessions via the ``patch_db_context`` fixture.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.tasks.celery_app import celery_app
from app.tasks.jobs import run_async
from app.validation_engine.journey_service import ensure_journey_service_registered
from app.validation_engine.models import (
    SyntheticActorType,
    ValidationRun,
    WorkflowRunStatus,
)
from app.validation_engine.orchestrator import ValidationOrchestrator
from app.validation_engine.synthetic import SyntheticActorFactory
from app.validation_engine.synthetic_journeys import get_journey_templates

logger = get_logger(__name__)

# A run in any of these states is considered in-flight.
IN_FLIGHT_STATUSES = (
    WorkflowRunStatus.pending,
    WorkflowRunStatus.queued,
    WorkflowRunStatus.running,
    WorkflowRunStatus.step_validating,
    WorkflowRunStatus.proof_generating,
    WorkflowRunStatus.remediation_checking,
)


async def has_inflight_run(db: AsyncSession, workflow_id: Any, journey: str) -> bool:
    """True when a synthetic run for the journey is still in flight."""
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(ValidationRun).where(
            ValidationRun.workflow_id == workflow_id,
            ValidationRun.status.in_(IN_FLIGHT_STATUSES),
            ValidationRun.created_at >= cutoff,
        )
    )
    for run in result.scalars().all():
        if (run.input_data or {}).get("journey") == journey:
            return True
    return False


async def run_synthetic_journeys(db: AsyncSession) -> Dict[str, Any]:
    """Queue one synthetic run per journey (bounded) and store a health snapshot.

    Split from the Celery task wrapper so tests can drive it with an explicit
    session.
    """
    from app.validation_engine.health import compute_and_store_snapshot
    from app.validation_engine.synthetic_journeys import ensure_journey_workflows

    ensure_journey_service_registered()

    templates = get_journey_templates()
    workflows = await ensure_journey_workflows(db, templates)

    actor_factory = SyntheticActorFactory()
    actor = await actor_factory.get_or_create_default_actor(db, SyntheticActorType.service)
    marker = (actor.markers or {}).get("synthetic_actor_id", actor.name)

    results: Dict[str, Any] = {}
    for journey_name in templates:
        workflow = workflows[journey_name]
        if await has_inflight_run(db, workflow.id, journey_name):
            logger.info("synthetic_journey_skipped_inflight", journey=journey_name)
            results[journey_name] = {"status": "skipped", "reason": "in-flight run"}
            continue

        suffix = uuid.uuid4().hex[:8]
        input_data = {
            "journey": journey_name,
            "synthetic": True,
            "actor_marker": marker,
            "project_name": f"synth-{journey_name}-{suffix}",
            "target_name": suffix,
        }
        orchestrator = ValidationOrchestrator(db)
        run = await orchestrator.create_run(
            workflow_id=str(workflow.id),
            trigger_event="synthetic_scheduled",
            input_data=input_data,
        )
        await actor_factory.mark_actor_used(db, actor)

        from app.validation_engine.tasks import execute_validation_run

        execute_validation_run.delay(str(run.id))
        results[journey_name] = {"status": "queued", "run_id": str(run.id)}
        logger.info("synthetic_journey_queued", journey=journey_name, run_id=str(run.id))

    snapshot = await compute_and_store_snapshot(db)
    results["_health_snapshot"] = {
        "score": snapshot.score,
        "consecutive_below_threshold": snapshot.consecutive_below_threshold,
    }
    return results


@celery_app.task(bind=True, max_retries=3)
def run_synthetic_validation(self):
    """Queue synthetic E2E journey runs and append a health snapshot.

    Runs every 15 minutes via Celery beat.
    """
    async def _work():
        from app.database import get_db_context

        async with get_db_context() as db:
            return await run_synthetic_journeys(db)

    try:
        return run_async(_work())
    except Exception as exc:  # noqa: BLE001 — task retries on transient failures
        logger.error("run_synthetic_validation_failed", error=str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
