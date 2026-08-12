"""Celery tasks for AI pre-audit document discovery and fetching."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import func, select

from app.core.logging import get_logger
from app.database import AsyncSessionLocal
from app.models import Lead, LeadDocument, LeadDocumentStatusEnum
from app.services.lead_intelligence.factory import get_scraper
from app.services.lead_intelligence.document_fetcher import RegistryDocumentFetcher
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)

MAX_DOCUMENT_FETCH_ATTEMPTS = 5
DOCUMENT_FETCH_RETRY_MINUTES = 60


def run_async(coro):
    """Run an async coroutine from a synchronous Celery task.

    Uses ``asyncio.run`` when no event loop is running (production) and
    falls back to running the coroutine on the current loop during tests.
    """
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
def fetch_lead_documents(self, lead_id: str) -> None:
    """Discover and download documents for a single lead."""

    async def _run():
        async with AsyncSessionLocal() as db:
            lead = await db.get(Lead, lead_id)
            if not lead:
                logger.warning("fetch_lead_documents_lead_not_found", lead_id=lead_id)
                return

            scraper = get_scraper(lead.registry_source.value)
            try:
                discovered = scraper.fetch_documents(lead)
                logger.info("lead_documents_discovered", lead_id=lead_id, count=len(discovered))

                # Upsert discovered documents
                existing_result = await db.execute(
                    select(LeadDocument).where(LeadDocument.lead_id == lead.id)
                )
                existing = {doc.source_url: doc for doc in existing_result.scalars().all()}

                docs_to_fetch: List[LeadDocument] = []
                for meta in discovered:
                    if meta["source_url"] in existing:
                        doc = existing[meta["source_url"]]
                        if doc.status != LeadDocumentStatusEnum.fetched:
                            docs_to_fetch.append(doc)
                    else:
                        doc = LeadDocument(
                            lead_id=lead.id,
                            document_type=meta["document_type"],
                            source_url=meta["source_url"],
                            title=meta.get("title"),
                            status=LeadDocumentStatusEnum.discovered,
                        )
                        db.add(doc)
                        docs_to_fetch.append(doc)

                await db.commit()

                # Fetch each discovered document
                fetcher = RegistryDocumentFetcher()
                try:
                    for doc in docs_to_fetch:
                        await fetcher.fetch_document(
                            doc,
                            lead_id=str(lead.id),
                            registry_source=lead.registry_source.value,
                        )
                        await db.commit()
                finally:
                    await fetcher.close()
            finally:
                scraper.close()

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("fetch_lead_documents_failed", lead_id=lead_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def fetch_all_pending_documents(self) -> None:
    """Fetch documents for all leads that have undiscovered or retryable documents.

    Leads are excluded when every document has either been fetched successfully,
    exhausted its retry budget, or failed within the retry cooldown window.
    """

    async def _run():
        async with AsyncSessionLocal() as db:
            retry_cutoff = datetime.now(timezone.utc) - timedelta(minutes=DOCUMENT_FETCH_RETRY_MINUTES)

            # A lead is pending if it has at least one document that is:
            #   - discovered (never fetched), or
            #   - failed with attempts remaining and outside the cooldown window.
            pending_doc = (
                (LeadDocument.status == LeadDocumentStatusEnum.discovered)
                | (
                    (LeadDocument.status == LeadDocumentStatusEnum.failed)
                    & (LeadDocument.fetch_attempts < MAX_DOCUMENT_FETCH_ATTEMPTS)
                    & (
                        (LeadDocument.last_fetch_attempt_at.is_(None))
                        | (LeadDocument.last_fetch_attempt_at < retry_cutoff)
                    )
                )
            )

            result = await db.execute(
                select(Lead.id)
                .where(Lead.documents.any(pending_doc))
                .distinct()
            )
            lead_ids = [str(row[0]) for row in result.all()]
            logger.info("fetch_all_pending_documents", count=len(lead_ids))
            for lead_id in lead_ids:
                fetch_lead_documents.delay(lead_id)

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("fetch_all_pending_documents_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)



from app.services.lead_intelligence.lead_converter import LeadToProjectConverter, LeadConversionError
from app.services.lead_intelligence.pre_audit_runner import PreAuditRunner
from app.models import LeadWorkflowStatusEnum, Project


@celery_app.task(bind=True, max_retries=3)
def convert_lead_to_project(self, lead_id: str) -> dict:
    """Convert a single qualified lead into a CarbonVerify project."""
    async def _run():
        async with AsyncSessionLocal() as db:
            lead = await db.get(Lead, lead_id)
            if not lead:
                logger.warning("convert_lead_not_found", lead_id=lead_id)
                return {"error": "lead not found"}

            try:
                converter = LeadToProjectConverter(db)
                project = await converter.convert(lead)
                run_pre_audit_for_project.delay(str(project.id), lead_id=str(lead.id))
                return {"project_id": str(project.id), "lead_id": lead_id}
            except LeadConversionError as exc:
                logger.warning("convert_lead_skipped", lead_id=lead_id, reason=str(exc))
                return {"error": str(exc)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("convert_lead_failed", lead_id=lead_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def run_pre_audit_for_project(self, project_id: str, lead_id: str | None = None) -> dict:
    """Run pre-audit workflow for a project."""
    async def _run():
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, project_id)
            if not project:
                logger.warning("pre_audit_project_not_found", project_id=project_id)
                return {"error": "project not found"}

            runner = PreAuditRunner(db)
            try:
                result = await runner.run_for_project(project, lead_id=lead_id)
                return {
                    "pre_audit_id": str(result.id),
                    "project_id": project_id,
                    "status": result.status.value,
                    "score": result.readiness_score,
                }
            except Exception as exc:
                logger.error("pre_audit_run_failed", project_id=project_id, error=str(exc))
                raise

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("run_pre_audit_for_project_failed", project_id=project_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def run_pre_audit_pipeline(self) -> dict:
    """Daily pipeline: convert qualified leads and run pre-audit."""
    async def _run():
        async with AsyncSessionLocal() as db:
            from datetime import date
            result = await db.execute(
                select(Lead).where(
                    Lead.lead_status.in_([LeadWorkflowStatusEnum.qualified, LeadWorkflowStatusEnum.proposal_sent]),
                    Lead.converted_project_id.is_(None),
                    Lead.crediting_period_start.isnot(None),
                    Lead.crediting_period_end.isnot(None),
                    Lead.documents.any(LeadDocument.status == LeadDocumentStatusEnum.fetched),
                )
            )
            leads = result.scalars().all()
            logger.info("pre_audit_pipeline_leads", count=len(leads))

            queued = []
            for lead in leads:
                convert_lead_to_project.delay(str(lead.id))
                queued.append(str(lead.id))
            return {"queued": queued, "count": len(queued)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("run_pre_audit_pipeline_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)
