"""Celery jobs for the methodology knowledge base.

``check_methodology_updates`` is a stub-safe daily poller: it never scrapes
registry sites or fetches copyrighted methodology PDFs on its own. Documents
are ingested only via the API / admin upload. The job simply counts documents
whose ``updated_at`` is older than the refresh horizon so operators can see
what is due for re-ingestion.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app import database as app_database
from app.core.logging import get_logger
from app.knowledge.models import MethodologyDocument
from app.tasks.celery_app import celery_app
from app.tasks.jobs import run_async

logger = get_logger(__name__)

REFRESH_HORIZON_DAYS = 90


@celery_app.task(name="app.tasks.knowledge_jobs.check_methodology_updates")
def check_methodology_updates() -> dict[str, Any]:
    """Count methodology documents due for refresh (``updated_at`` > 90 days).

    Network fetching is intentionally NOT implemented here: methodology texts
    enter the knowledge base only through the ingest API / admin upload.
    """
    async def _check() -> dict[str, Any]:
        async with app_database.get_db_context() as db:
            total_result = await db.execute(select(func.count()).select_from(MethodologyDocument))
            total = total_result.scalar_one()

            cutoff = datetime.now(UTC) - timedelta(days=REFRESH_HORIZON_DAYS)
            # SQLite returns naive datetimes; fetch candidates and compare in
            # Python so the horizon check is correct on every backend.
            result = await db.execute(select(MethodologyDocument.updated_at))
            updated_ats = [row[0] for row in result.all()]
            due = 0
            for updated_at in updated_ats:
                if updated_at is None:
                    due += 1
                    continue
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=UTC)
                if updated_at < cutoff:
                    due += 1
            return {
                "total_documents": total,
                "due_for_refresh": due,
                "refresh_horizon_days": REFRESH_HORIZON_DAYS,
                "fetching": "disabled — ingest via API/admin upload only",
            }

    summary = run_async(_check())
    logger.info(
        "methodology_update_check_complete",
        total_documents=summary["total_documents"],
        due_for_refresh=summary["due_for_refresh"],
    )
    return summary
