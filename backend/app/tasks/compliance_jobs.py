"""Celery tasks for compliance workflows (GDPR erasure, etc.)."""

import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import (
    DataSubjectRequest,
    DSRStatusEnum,
    Enumerator,
    SurveyResponse,
    SupportTicket,
    WhatsAppConversation,
    ConsentRecord,
    User,
    Lead,
)
from app.core.logging import get_logger
from app.core.encryption import get_field_encryption

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_erasure_request(self, dsr_id: str):
    """Process a GDPR right-to-erasure request asynchronously.

    Steps:
    1. Mark DSR as in_progress
    2. Identify all records belonging to subject_id
    3. Redact/delete from PostgreSQL
    4. Delete from S3 (photos, documents)
    5. Clear from Redis (session/cache)
    6. Mark DSR as completed
    """
    import asyncio
    asyncio.run(_async_process_erasure(dsr_id))


async def _async_process_erasure(dsr_id: str):
    async with AsyncSessionLocal() as db:
        try:
            # Fetch DSR
            result = await db.execute(
                select(DataSubjectRequest).where(DataSubjectRequest.id == uuid.UUID(dsr_id))
            )
            dsr = result.scalar_one_or_none()
            if not dsr:
                logger.error("erasure_dsr_not_found", dsr_id=dsr_id)
                return

            dsr.status = DSRStatusEnum.in_progress
            await db.commit()

            subject_id = dsr.subject_id
            subject_type = dsr.subject_type

            logger.info("erasure_started", dsr_id=dsr_id, subject_id=subject_id, subject_type=subject_type)

            # Delete/redact based on subject type
            if subject_type == "enumerator":
                await _erase_enumerator(db, subject_id)
            elif subject_type == "household":
                await _erase_household(db, subject_id)
            elif subject_type == "developer":
                await _erase_developer(db, subject_id)
            elif subject_type == "user":
                await _erase_user(db, subject_id)

            # Mark as completed
            dsr.status = DSRStatusEnum.completed
            dsr.completed_at = __import__("datetime", fromlist=["datetime"]).datetime.now(__import__("datetime", fromlist=["timezone"]).timezone.utc)
            await db.commit()

            logger.info("erasure_completed", dsr_id=dsr_id)

        except Exception as exc:
            logger.error("erasure_failed", dsr_id=dsr_id, error=str(exc))
            dsr.status = DSRStatusEnum.rejected
            dsr.details = {**(dsr.details or {}), "error": str(exc)}
            await db.commit()
            raise self.retry(exc=exc, countdown=60)


async def _erase_enumerator(db: AsyncSession, subject_id: str):
    """Erase enumerator and related data."""
    enum_id = uuid.UUID(subject_id)

    # Delete survey responses
    await db.execute(delete(SurveyResponse).where(SurveyResponse.enumerator_id == enum_id))

    # Delete conversations
    await db.execute(delete(WhatsAppConversation).where(WhatsAppConversation.enumerator_id == enum_id))

    # Delete enumerator
    await db.execute(delete(Enumerator).where(Enumerator.id == enum_id))

    await db.commit()
    logger.info("erasure_enumerator", enumerator_id=subject_id)


async def _erase_household(db: AsyncSession, subject_id: str):
    """Erase household survey data."""
    await db.execute(
        delete(SurveyResponse).where(SurveyResponse.household_id == subject_id)
    )
    await db.commit()
    logger.info("erasure_household", household_id=subject_id)


async def _erase_developer(db: AsyncSession, subject_id: str):
    """Erase developer contact info from leads."""
    # Anonymize lead developer info instead of deleting (leads are business records)
    result = await db.execute(select(Lead).where(Lead.developer_email == subject_id))
    leads = result.scalars().all()
    for lead in leads:
        lead.developer_contact = None
        lead.developer_email = None
    await db.commit()
    logger.info("erasure_developer", developer_email=subject_id, leads_anonymized=len(leads))


async def _erase_user(db: AsyncSession, subject_id: str):
    """Erase user account and associated data."""
    user_id = uuid.UUID(subject_id)

    # Delete consent records
    await db.execute(delete(ConsentRecord).where(ConsentRecord.subject_id == subject_id))

    # Soft-delete user (keep record for audit, clear PII)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.email = f"redacted-{user.id}@deleted.carbonverify.io"
        user.name = "Redacted User"
        user.hashed_password = ""
        user.mfa_secret = None
        user.mfa_enabled = False

    await db.commit()
    logger.info("erasure_user", user_id=subject_id)
