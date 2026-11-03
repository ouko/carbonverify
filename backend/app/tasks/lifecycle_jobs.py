"""Autonomous lifecycle Celery jobs.

- ``advance_project_task``: advance a single project through lifecycle states.
- ``lifecycle_scan``: beat-driven scan that enqueues advancement for projects
  whose current-state agent runs are all high-confidence (or never ran).
- ``human_review_sla_sweep``: beat-driven sweep that auto-approves stale
  pending human review items after 24h.

DB access goes through ``app.database.get_db_context`` so tests can route it
to the session fixture via the ``patch_db_context`` conftest fixture.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

# Imported at call time inside tasks (app.database.get_db_context) so the
# test-suite monkeypatch of app.database.get_db_context routes task DB
# sessions to the test engine.
from app import database as app_database
from app.core.logging import get_logger
from app.models import AgentRun, HumanReviewQueue, Project, QueueStatusEnum
from app.orchestrator.orchestrator import (
    LIFECYCLE_DRIVE_STATES,
    STATE_TRANSITIONS,
    KimiClawOrchestrator,
)
from app.tasks.celery_app import celery_app
from app.tasks.jobs import run_async

logger = get_logger(__name__)

SLA_MAX_AGE = timedelta(hours=24)
RECENT_PROJECT_WINDOW = timedelta(days=7)


@celery_app.task(bind=True, max_retries=3)
def advance_project_task(self, project_id: str):
    """Advance a single project autonomously (see orchestrator.advance_project)."""
    async def _advance():
        async with app_database.get_db_context() as db:
            orchestrator = KimiClawOrchestrator(db)
            return await orchestrator.advance_project(uuid.UUID(project_id))

    try:
        result = run_async(_advance())
        logger.info("advance_project_task_completed", project_id=project_id)
        return result
    except Exception as exc:
        logger.error("advance_project_task_failed", project_id=project_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def lifecycle_scan(self):
    """Enqueue advance_project_task for projects ready to move forward.

    Considers only projects in lifecycle-driveable states (onboarding →
    submitted) created/updated in the last 7 days. A project is enqueued when
    every required agent for its current state has a most recent run with
    confidence >= 0.95, or when agents have never run in that state.
    """
    async def _scan():
        enqueued = 0
        skipped = 0
        async with app_database.get_db_context() as db:
            cutoff = datetime.now(timezone.utc) - RECENT_PROJECT_WINDOW
            result = await db.execute(
                select(Project).where(
                    Project.status.in_(LIFECYCLE_DRIVE_STATES),
                    Project.created_at >= cutoff,
                )
            )
            projects = result.scalars().all()

            for project in projects:
                transitions = STATE_TRANSITIONS.get(project.status, {})
                if not transitions:
                    skipped += 1
                    continue
                _, agent_types = next(iter(transitions.items()))

                all_high_confidence = True
                never_ran = False
                for agent_type in agent_types:
                    run_result = await db.execute(
                        select(AgentRun)
                        .where(
                            AgentRun.project_id == project.id,
                            AgentRun.agent_type == agent_type,
                        )
                        .order_by(AgentRun.created_at.desc())
                        .limit(1)
                    )
                    latest = run_result.scalar_one_or_none()
                    if latest is None:
                        never_ran = True
                        break
                    if (latest.confidence_score or 0.0) < 0.95:
                        all_high_confidence = False

                if never_ran or all_high_confidence:
                    advance_project_task.delay(str(project.id))
                    enqueued += 1
                    logger.info(
                        "lifecycle_scan_enqueued",
                        project_id=str(project.id),
                        state=project.status.value,
                        never_ran=never_ran,
                    )
                else:
                    skipped += 1

        return {"projects_checked": len(projects), "enqueued": enqueued, "skipped": skipped}

    try:
        result = run_async(_scan())
        logger.info("lifecycle_scan_completed", **result)
        return result
    except Exception as exc:
        logger.error("lifecycle_scan_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def human_review_sla_sweep(self):
    """Auto-approve pending human review items older than 24h (priority <= 3)."""
    async def _sweep():
        auto_approved = 0
        async with app_database.get_db_context() as db:
            cutoff = datetime.now(timezone.utc) - SLA_MAX_AGE
            result = await db.execute(
                select(HumanReviewQueue).where(
                    HumanReviewQueue.status == QueueStatusEnum.pending,
                    HumanReviewQueue.priority <= 3,
                    HumanReviewQueue.created_at < cutoff,
                )
            )
            items = result.scalars().all()

            orchestrator = KimiClawOrchestrator(db)
            for item in items:
                outcome = await orchestrator.sla_auto_approve(item.id, max_age=SLA_MAX_AGE)
                if outcome.get("error"):
                    logger.warning(
                        "sla_sweep_item_skipped",
                        queue_item_id=str(item.id),
                        reason=outcome["error"],
                    )
                    continue
                auto_approved += 1
                logger.info("sla_sweep_auto_approved", queue_item_id=str(item.id))

        return {"stale_items_found": len(items), "auto_approved": auto_approved}

    try:
        result = run_async(_sweep())
        logger.info("human_review_sla_sweep_completed", **result)
        return result
    except Exception as exc:
        logger.error("human_review_sla_sweep_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)
