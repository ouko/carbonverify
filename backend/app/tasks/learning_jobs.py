"""Celery jobs for the agent learning loop.

The weekly beat task generates the retraining brief and persists it as a
``learning_reports`` row so the dashboard/API can read the latest stored
snapshot without recomputation.
"""

import uuid
from typing import Any

from app import database as app_database
from app.core.logging import get_logger
from app.learning.service import LearningLoopService
from app.tasks.celery_app import celery_app
from app.tasks.jobs import run_async

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.learning_jobs.generate_weekly_learning_report")
def generate_weekly_learning_report() -> dict[str, Any]:
    """Generate the weekly agent retraining report and store it."""
    async def _generate() -> dict[str, Any]:
        async with app_database.get_db_context() as db:
            service = LearningLoopService(db)
            report = await service.weekly_retraining_report(persist=True)
            # Ensure JSON-serializability for the Celery result backend.
            return {
                "report_id": str(uuid.uuid4()),
                "generated_at": report["generated_at"],
                "agent_count": len(report["agents"]),
                "suggested_adjustments": report["suggested_adjustments"],
                "markdown": report["markdown"],
            }

    summary = run_async(_generate())
    logger.info(
        "weekly_learning_report_generated",
        agent_count=summary["agent_count"],
        adjustments=len(summary["suggested_adjustments"]),
    )
    return summary
