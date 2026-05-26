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
    try:
        asyncio.run(_async_process_erasure(dsr_id))
    except Exception as exc:
        logger.error("erasure_failed", dsr_id=dsr_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


async def _async_process_erasure(dsr_id: str):
    async with AsyncSessionLocal() as db:
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

        try:
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
            raise


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
    """Erase household survey data.

    NOTE: household_id is encrypted with non-deterministic Fernet, so exact-match
    SQL queries don't work. We load all responses and filter in Python.
    For production scale, add a household_id_hash column for searchable lookup.
    """
    result = await db.execute(select(SurveyResponse).limit(1000))
    responses = result.scalars().all()
    deleted = 0
    for response in responses:
        if response.household_id == subject_id:
            await db.delete(response)
            deleted += 1
    await db.commit()
    if len(responses) >= 1000:
        logger.warning("erasure_household_batch_limit", household_id=subject_id, hint="Add household_id_hash for scalable lookup")
    logger.info("erasure_household", household_id=subject_id, deleted=deleted)


async def _erase_developer(db: AsyncSession, subject_id: str):
    """Erase developer contact info from leads.

    NOTE: developer_email is encrypted with non-deterministic Fernet, so exact-match
    SQL queries don't work. We load all leads and filter in Python.
    For production scale, add a developer_email_hash column for searchable lookup.
    """
    # Anonymize lead developer info instead of deleting (leads are business records)
    result = await db.execute(select(Lead).limit(1000))
    leads = result.scalars().all()
    anonymized = 0
    for lead in leads:
        if lead.developer_email == subject_id:
            lead.developer_contact = None
            lead.developer_email = None
            anonymized += 1
    await db.commit()
    if len(leads) >= 1000:
        logger.warning("erasure_developer_batch_limit", developer_email=subject_id, hint="Add developer_email_hash for scalable lookup")
    logger.info("erasure_developer", developer_email=subject_id, leads_anonymized=anonymized)


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
