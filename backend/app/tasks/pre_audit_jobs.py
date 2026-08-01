"""Celery tasks for AI pre-audit document discovery and fetching."""

import asyncio
from datetime import datetime, timezone
from typing import List

from celery.exceptions import Retry
from sqlalchemy import select

from app.core.logging import get_logger
from app.database import AsyncSessionLocal
from app.models import Lead, LeadDocument, LeadDocumentStatusEnum
from app.services.lead_intelligence.factory import get_scraper
from app.services.lead_intelligence.document_fetcher import RegistryDocumentFetcher
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


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
                        await fetcher.fetch_document(doc)
                        await db.commit()
                finally:
                    fetcher.close()
            finally:
                scraper.close()

    try:
        run_async(_run())
    except Retry:
        raise
    except Exception as exc:
        logger.error("fetch_lead_documents_failed", lead_id=lead_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def fetch_all_pending_documents(self) -> None:
    """Fetch documents for all leads that have no fetched documents yet."""

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Lead.id).where(
                    ~Lead.documents.any(LeadDocument.status == LeadDocumentStatusEnum.fetched)
                )
            )
            lead_ids = [str(row[0]) for row in result.all()]
            logger.info("fetch_all_pending_documents", count=len(lead_ids))
            for lead_id in lead_ids:
                fetch_lead_documents.delay(lead_id)

    try:
        run_async(_run())
    except Retry:
        raise
    except Exception as exc:
        logger.error("fetch_all_pending_documents_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)
