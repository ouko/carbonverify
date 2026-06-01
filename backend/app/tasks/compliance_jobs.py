"""Celery tasks for compliance workflows (GDPR erasure, etc.)."""

import secrets
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.auth.security import get_password_hash
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
    RefreshToken,
    UserInvite,
    BuyerProfile,
    ConflictOfInterest,
    HumanReviewQueue,
    Developer,
    AuditLog,
)
from app.core.logging import get_logger
from app.core.encryption import get_field_encryption
from app.auth.sessions import SessionManager

logger = get_logger(__name__)

# Conditional boto3 import for environments without AWS SDK
try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore

ANONYMIZED_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


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
        if self.request.retries >= self.max_retries:
            # Final failure - mark as rejected
            asyncio.run(_mark_dsr_rejected(dsr_id, str(exc)))
        raise self.retry(exc=exc, countdown=60)


async def _mark_dsr_rejected(dsr_id: str, error_msg: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DataSubjectRequest).where(DataSubjectRequest.id == uuid.UUID(dsr_id))
        )
        dsr = result.scalar_one_or_none()
        if dsr:
            dsr.status = DSRStatusEnum.rejected
            dsr.rejection_reason = error_msg
            await db.commit()


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
        dsr.completed_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info("erasure_completed", dsr_id=dsr_id)


async def _erase_enumerator(db: AsyncSession, subject_id: str):
    """Erase enumerator and related data."""
    enum_id = uuid.UUID(subject_id)

    # Extract S3 keys from survey responses before deleting
    result = await db.execute(select(SurveyResponse).where(SurveyResponse.enumerator_id == enum_id))
    responses = result.scalars().all()
    s3_keys = []
    for resp in responses:
        for photo in (resp.photos or []):
            if isinstance(photo, str):
                s3_keys.append(photo)
            elif isinstance(photo, dict):
                key = photo.get("s3_key") or photo.get("key")
                if key:
                    s3_keys.append(key)

    # Delete survey responses
    await db.execute(delete(SurveyResponse).where(SurveyResponse.enumerator_id == enum_id))

    # Delete conversations
    await db.execute(delete(WhatsAppConversation).where(WhatsAppConversation.assigned_enumerator_id == enum_id))

    # Delete enumerator
    await db.execute(delete(Enumerator).where(Enumerator.id == enum_id))

    await db.commit()

    # Delete S3 objects
    if s3_keys and boto3 is not None:
        from app.config import get_settings
        settings = get_settings()
        s3 = boto3.client("s3")
        for s3_key in s3_keys:
            try:
                s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
            except Exception as e:
                logger.warning("s3_delete_failed", key=s3_key, error=str(e))

    logger.info("erasure_enumerator", enumerator_id=subject_id, s3_keys_deleted=len(s3_keys))


async def _erase_household(db: AsyncSession, subject_id: str):
    """Erase household survey data.

    NOTE: household_id is encrypted with non-deterministic Fernet, so exact-match
    SQL queries don't work. We load all responses and filter in Python.
    For production scale, add a household_id_hash column for searchable lookup.
    """
    batch_size = 500
    offset = 0
    total_deleted = 0
    while True:
        result = await db.execute(select(SurveyResponse).offset(offset).limit(batch_size))
        responses = result.scalars().all()
        if not responses:
            break
        s3_keys = []
        for response in responses:
            if response.household_id == subject_id:
                for photo in (response.photos or []):
                    if isinstance(photo, str):
                        s3_keys.append(photo)
                    elif isinstance(photo, dict):
                        key = photo.get("s3_key") or photo.get("key")
                        if key:
                            s3_keys.append(key)
                await db.delete(response)
                total_deleted += 1
        await db.commit()

        # Delete S3 objects for this batch
        if s3_keys and boto3 is not None:
            from app.config import get_settings
            settings = get_settings()
            s3 = boto3.client("s3")
            for s3_key in s3_keys:
                try:
                    s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
                except Exception as e:
                    logger.warning("s3_delete_failed", key=s3_key, error=str(e))

        if len(responses) < batch_size:
            break
        offset += batch_size

    logger.info("erasure_household_complete", household_id=subject_id, deleted=total_deleted)


async def _erase_developer(db: AsyncSession, subject_id: str):
    """Erase developer contact info from leads.

    NOTE: developer_email is encrypted with non-deterministic Fernet, so exact-match
    SQL queries don't work. We load all leads and filter in Python.
    For production scale, add a developer_email_hash column for searchable lookup.
    """
    # Anonymize lead developer info instead of deleting (leads are business records)
    batch_size = 500
    offset = 0
    total_anonymized = 0
    while True:
        result = await db.execute(select(Lead).offset(offset).limit(batch_size))
        leads = result.scalars().all()
        if not leads:
            break
        for lead in leads:
            if lead.developer_email == subject_id:
                lead.developer_contact = None
                lead.developer_email = None
                total_anonymized += 1
        await db.commit()
        if len(leads) < batch_size:
            break
        offset += batch_size

    logger.info("erasure_developer_complete", developer_email=subject_id, leads_anonymized=total_anonymized)


async def _erase_user(db: AsyncSession, subject_id: str):
    """Erase user account and associated data."""
    user_id = uuid.UUID(subject_id)

    # Delete consent records
    await db.execute(delete(ConsentRecord).where(ConsentRecord.subject_id == subject_id))

    # Delete refresh tokens
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))

    # Delete user invites created by or used by this user
    await db.execute(
        delete(UserInvite).where(
            (UserInvite.invited_by == user_id) | (UserInvite.used_by_user_id == user_id)
        )
    )

    # Delete buyer profiles
    await db.execute(delete(BuyerProfile).where(BuyerProfile.user_id == user_id))

    # Delete conflicts of interest
    await db.execute(delete(ConflictOfInterest).where(ConflictOfInterest.user_id == user_id))

    # Unassign from human review queue
    await db.execute(
        update(HumanReviewQueue)
        .where(HumanReviewQueue.assigned_to == user_id)
        .values(assigned_to=None)
    )

    # Unassign from support tickets
    await db.execute(
        update(SupportTicket)
        .where(SupportTicket.assigned_to == user_id)
        .values(assigned_to=None)
    )

    # Anonymize audit logs
    await db.execute(
        update(AuditLog)
        .where(AuditLog.actor_id == user_id)
        .values(actor_id=ANONYMIZED_ACTOR_ID)
    )

    # Soft-delete user (keep record for audit, clear PII)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.email = f"redacted-{user.id}@deleted.carbonverify.io"
        user.name = "Redacted User"
        user.hashed_password = get_password_hash(secrets.token_urlsafe(32))
        user.mfa_secret = None
        user.mfa_enabled = False
        user.is_active = False

        # Redact developer profile if present
        dev_result = await db.execute(select(Developer).where(Developer.user_id == user_id))
        developer = dev_result.scalar_one_or_none()
        if developer:
            developer.contact_phone = ""
            developer.company_name = ""

    await db.commit()

    # Clear Redis sessions
    await SessionManager.destroy_all_user_sessions(subject_id)

    logger.info("erasure_user", user_id=subject_id)
