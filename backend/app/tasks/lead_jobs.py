"""Celery tasks for lead intelligence engine."""

import asyncio
from datetime import datetime, timezone, date, timedelta

from sqlalchemy import select

from app.tasks.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import Lead, LeadWorkflowStatusEnum, ScraperRun
from app.services.lead_intelligence.scorer import score_lead, priority_from_score
from app.services.lead_intelligence.factory import get_scraper, list_scrapers
from app.core.logging import get_logger

logger = get_logger(__name__)


def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


@celery_app.task(bind=True, max_retries=3)
def scrape_registries(self, country: str = "Kenya"):
    """Daily scrape of all configured registries."""
    logger.info("task_scrape_registries_started", country=country)

    async def _scrape():
        async with AsyncSessionLocal() as db:
            total_created = 0
            total_updated = 0

            for source in list_scrapers():
                scraper = get_scraper(source)
                raw_leads: list[dict] = []
                error_msg: str | None = None
                data_source = "demo"
                source_created = 0
                source_updated = 0

                try:
                    raw_leads = scraper.scrape(country=country)
                except Exception as exc:
                    error_msg = str(exc)
                    logger.error("scrape_failed", source=source, error=error_msg)
                finally:
                    scraper.close()

                for raw in raw_leads:
                    meta = raw.pop("_scrape_meta", {})
                    data_source = meta.get("data_source", "demo")

                    existing = await db.execute(
                        select(Lead).where(
                            Lead.registry_source == source,
                            Lead.external_id == raw["external_id"],
                        )
                    )
                    lead = existing.scalar_one_or_none()

                    cp_end = None
                    if raw.get("crediting_period_end"):
                        cp_end = date.fromisoformat(raw["crediting_period_end"])
                    lv_date = None
                    if raw.get("last_verification_date"):
                        lv_date = date.fromisoformat(raw["last_verification_date"])

                    stuck = score_lead(
                        days_in_status=raw.get("days_in_status"),
                        status=raw.get("status", "unknown"),
                        crediting_period_end=cp_end,
                        last_verification_date=lv_date,
                        methodology=raw.get("methodology"),
                    )
                    priority = priority_from_score(stuck)

                    if lead:
                        for key in ["project_name", "project_developer", "developer_contact",
                                    "developer_email", "country", "region", "methodology", "sector",
                                    "status", "estimated_credits_per_year", "registry_url", "days_in_status"]:
                            if key in raw and raw[key] is not None:
                                setattr(lead, key, raw[key])
                        lead.stuck_score = stuck
                        lead.priority = priority
                        lead.last_scored_at = datetime.now(timezone.utc)
                        lead.updated_at = datetime.now(timezone.utc)
                        total_updated += 1
                        source_updated += 1
                    else:
                        lead_data = {
                            "registry_source": source,
                            "external_id": raw["external_id"],
                            "project_name": raw.get("project_name", ""),
                            "project_developer": raw.get("project_developer"),
                            "developer_contact": raw.get("developer_contact"),
                            "developer_email": raw.get("developer_email"),
                            "country": raw.get("country"),
                            "region": raw.get("region"),
                            "methodology": raw.get("methodology"),
                            "sector": raw.get("sector"),
                            "status": raw.get("status", "unknown"),
                            "estimated_credits_per_year": raw.get("estimated_credits_per_year"),
                            "registry_url": raw.get("registry_url"),
                            "days_in_status": raw.get("days_in_status"),
                            "stuck_score": stuck,
                            "priority": priority,
                            "scraped_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        }
                        if raw.get("crediting_period_start"):
                            lead_data["crediting_period_start"] = date.fromisoformat(raw["crediting_period_start"])
                        if raw.get("crediting_period_end"):
                            lead_data["crediting_period_end"] = date.fromisoformat(raw["crediting_period_end"])
                        if raw.get("last_verification_date"):
                            lead_data["last_verification_date"] = date.fromisoformat(raw["last_verification_date"])

                        db.add(Lead(**lead_data))
                        total_created += 1
                        source_created += 1

                # Log this scrape run
                db.add(ScraperRun(
                    source=source,
                    scraped_at=datetime.now(timezone.utc),
                    count=len(raw_leads),
                    created=source_created,
                    updated=source_updated,
                    status="error" if error_msg else ("live" if data_source == "live" else "demo"),
                    data_source=data_source,
                    error_message=error_msg,
                    mode=scraper.live_mode and "live" or "demo",
                ))

            await db.commit()
            logger.info("task_scrape_registries_completed", created=total_created, updated=total_updated)
            return {"created": total_created, "updated": total_updated}

    try:
        return run_async(_scrape())
    except Exception as exc:
        logger.error("task_scrape_registries_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(bind=True, max_retries=3)
def score_leads(self):
    """Weekly re-score of all unconverted leads."""
    logger.info("task_score_leads_started")

    async def _score():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Lead).where(Lead.lead_status != LeadWorkflowStatusEnum.converted)
            )
            leads = result.scalars().all()
            updated = 0

            for lead in leads:
                status_str = lead.status.value if hasattr(lead.status, "value") else str(lead.status)
                lead.stuck_score = score_lead(
                    days_in_status=lead.days_in_status,
                    status=status_str,
                    crediting_period_end=lead.crediting_period_end,
                    last_verification_date=lead.last_verification_date,
                    methodology=lead.methodology,
                )
                lead.priority = priority_from_score(lead.stuck_score)
                lead.last_scored_at = datetime.now(timezone.utc)
                lead.updated_at = datetime.now(timezone.utc)
                updated += 1

            await db.commit()
            logger.info("task_score_leads_completed", updated=updated)
            return {"updated": updated}

    try:
        return run_async(_score())
    except Exception as exc:
        logger.error("task_score_leads_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(bind=True, max_retries=3)
def check_lead_deadlines(self):
    """Daily check for leads with approaching crediting period deadlines."""
    logger.info("task_check_lead_deadlines_started")

    async def _check():
        async with AsyncSessionLocal() as db:
            threshold = date.today() + timedelta(days=30)
            result = await db.execute(
                select(Lead).where(
                    Lead.crediting_period_end <= threshold,
                    Lead.crediting_period_end >= date.today(),
                    Lead.lead_status != LeadWorkflowStatusEnum.converted,
                )
            )
            leads = result.scalars().all()
            flagged = 0

            for lead in leads:
                lead.stuck_score = min(lead.stuck_score + 15.0, 100.0)
                lead.priority = priority_from_score(lead.stuck_score)
                lead.updated_at = datetime.now(timezone.utc)
                flagged += 1

            await db.commit()
            logger.info("task_check_lead_deadlines_completed", flagged=flagged)
            return {"flagged": flagged}

    try:
        return run_async(_check())
    except Exception as exc:
        logger.error("task_check_lead_deadlines_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(bind=True, max_retries=3)
def fetch_lead_documents_task(self, lead_id: str):
    """Stub: queue lead document fetching for a single lead.

    Full implementation will scan the lead's registry URL, discover linked
    documents, persist LeadDocument rows, and fetch them into S3.
    """
    logger.info("task_fetch_lead_documents_started", lead_id=lead_id)
    # TODO: implement document discovery and fetching in Task 6
    return {"lead_id": lead_id, "status": "queued"}
