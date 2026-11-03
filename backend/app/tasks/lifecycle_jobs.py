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
from datetime import UTC, datetime, timedelta

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
            cutoff = datetime.now(UTC) - RECENT_PROJECT_WINDOW
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
            cutoff = datetime.now(UTC) - SLA_MAX_AGE
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


REMEDIATION_SWEEP_MAX_AGE = timedelta(hours=1)
REMEDIATION_SWEEP_BATCH = 50


@celery_app.task(bind=True, max_retries=3)
def remediation_sweep(self):
    """Re-run failed remediations whose latest attempt is older than 1 hour.

    Each stale target gets a fresh attempt budget (``attempts_so_far=0``);
    the failing state is recovered from the last attempt's persisted detail.
    Bounded at 50 targets per run. The engine itself escalates targets whose
    fresh round also fails.
    """
    from app.remediation.engine import RemediationEngine
    from app.remediation.models import RemediationAttempt

    async def _sweep():
        reruns = 0
        async with app_database.get_db_context() as db:
            cutoff = datetime.now(UTC) - REMEDIATION_SWEEP_MAX_AGE
            result = await db.execute(
                select(RemediationAttempt)
                .where(
                    RemediationAttempt.status == "failed",
                    RemediationAttempt.created_at < cutoff,
                )
                .order_by(RemediationAttempt.created_at.desc())
                .limit(REMEDIATION_SWEEP_BATCH)
            )
            rows = result.scalars().all()

            # Deduplicate to the most recent failed attempt per target.
            latest_by_target: dict[tuple, RemediationAttempt] = {}
            for row in rows:
                key = (row.rule_key, row.target_type, row.target_id)
                latest_by_target.setdefault(key, row)

            for (rule_key, target_type, target_id), row in latest_by_target.items():
                failing_state = (row.detail or {}).get("failing_state")
                if not isinstance(failing_state, dict):
                    logger.warning(
                        "remediation_sweep_skipped",
                        rule_key=rule_key,
                        target_type=target_type,
                        target_id=target_id,
                        reason="no failing_state snapshot on attempt",
                    )
                    continue
                engine = RemediationEngine(db)
                outcome = await engine.remediate(
                    rule_key,
                    target_type,
                    target_id,
                    failing_state,
                    project_id=row.project_id,
                    attempts_so_far=0,
                )
                reruns += 1
                logger.info(
                    "remediation_sweep_rerun",
                    rule_key=rule_key,
                    target_type=target_type,
                    target_id=target_id,
                    status=outcome.status,
                )

        return {"stale_targets": len(latest_by_target), "rerun": reruns}

    try:
        result = run_async(_sweep())
        logger.info("remediation_sweep_completed", **result)
        return result
    except Exception as exc:
        logger.error("remediation_sweep_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)
