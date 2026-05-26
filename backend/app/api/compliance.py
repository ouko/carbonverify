"""
Compliance API for CarbonVerify.

Implements:
- Kenya Data Protection Act compliance (consent, DSR, breach notification)
- Independence enforcement (conflict-of-interest detection)
- Methodology versioning
"""

import uuid
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import (
    User, ConsentRecord, ConsentTypeEnum, DataSubjectRequest,
    DSRTypeEnum, DSRStatusEnum, BreachNotification, BreachStatusEnum,
    ConflictOfInterest, MethodologyVersion, AuditActionEnum,
)
from app.auth.dependencies import require_admin, require_operator, get_current_user
from app.security.audit_logging import AuditLogger
from app.core.logging import get_logger
from app.config import get_settings

settings = get_settings()
logger = get_logger(__name__)
router = APIRouter(prefix="/compliance", tags=["compliance"])


# ─── Request Schemas ──────────────────────────────────────────────────────────

class ConsentRequest(BaseModel):
    subject_id: str
    subject_type: str
    consent_type: ConsentTypeEnum
    granted: bool = True
    project_id: Optional[uuid.UUID] = None
    method: str = "explicit"


class DSRRequest(BaseModel):
    request_type: DSRTypeEnum
    subject_id: str
    subject_type: str
    description: Optional[str] = None


class BreachReportRequest(BaseModel):
    title: str
    description: str
    severity: str
    affected_subjects_count: Optional[int] = None
    affected_data_types: Optional[List[str]] = None


class BreachUpdateRequest(BaseModel):
    status: BreachStatusEnum
    containment_measures: Optional[str] = None


class COIRequest(BaseModel):
    project_id: uuid.UUID
    relationship_type: str
    description: str


class MethodologyCreateRequest(BaseModel):
    methodology_name: str
    version: str
    effective_date: date
    rules_json: dict
    change_summary: str


class DSRUpdateRequest(BaseModel):
    status: Optional[DSRStatusEnum] = None
    assigned_to: Optional[uuid.UUID] = None
    fulfillment_notes: Optional[str] = None
    rejection_reason: Optional[str] = None


class MethodologyUpdateRequest(BaseModel):
    status: Optional[DSRStatusEnum] = None
    assigned_to: Optional[uuid.UUID] = None
    fulfillment_notes: Optional[str] = None
    rejection_reason: Optional[str] = None


class COIReviewRequest(BaseModel):
    approved: bool
    review_notes: Optional[str] = None


# ─── Consent Management ───────────────────────────────────────────────────────

@router.post("/consent", status_code=status.HTTP_201_CREATED)
async def record_consent(
    payload: ConsentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a consent decision."""
    record = ConsentRecord(
        subject_id=payload.subject_id,
        subject_type=payload.subject_type,
        consent_type=payload.consent_type,
        granted=payload.granted,
        project_id=payload.project_id,
        method=payload.method,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.consent_given if payload.granted else AuditActionEnum.consent_revoked,
        actor_id=current_user.id,
        target_type="consent",
        target_id=record.id,
        metadata={"subject_id": payload.subject_id, "consent_type": payload.consent_type.value},
    )

    return {"id": str(record.id), "granted": payload.granted, "recorded_at": record.granted_at}


@router.get("/consent/{subject_id}")
async def get_consent_status(
    subject_id: str,
    consent_type: Optional[ConsentTypeEnum] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get current consent status for a subject."""
    stmt = select(ConsentRecord).where(ConsentRecord.subject_id == subject_id)
    if consent_type:
        stmt = stmt.where(ConsentRecord.consent_type == consent_type)
    stmt = stmt.order_by(desc(ConsentRecord.granted_at))

    result = await db.execute(stmt)
    records = result.scalars().all()

    if not records:
        return {"subject_id": subject_id, "has_consent": False, "records": []}

    latest = records[0]
    return {
        "subject_id": subject_id,
        "has_consent": latest.granted and latest.revoked_at is None,
        "latest_record": {
            "type": latest.consent_type.value,
            "granted": latest.granted,
            "granted_at": latest.granted_at,
            "revoked_at": latest.revoked_at,
        },
        "records": [
            {
                "type": r.consent_type.value,
                "granted": r.granted,
                "granted_at": r.granted_at,
                "method": r.method,
            }
            for r in records
        ],
    }


# ─── Data Subject Requests (DSR) ──────────────────────────────────────────────

@router.post("/dsr", status_code=status.HTTP_201_CREATED)
async def submit_dsr(
    payload: DSRRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a Data Subject Request (public endpoint)."""
    sla_deadline = datetime.now(timezone.utc) + timedelta(days=settings.DSR_RESPONSE_SLA_DAYS)

    dsr = DataSubjectRequest(
        request_type=payload.request_type,
        subject_id=payload.subject_id,
        subject_type=payload.subject_type,
        description=payload.description,
        sla_deadline=sla_deadline,
    )
    db.add(dsr)
    await db.commit()
    await db.refresh(dsr)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.dsr_received,
        actor_id=None,
        target_type="dsr",
        target_id=dsr.id,
        metadata={"request_type": payload.request_type.value, "subject_id": payload.subject_id},
    )

    return {
        "id": str(dsr.id),
        "status": dsr.status.value,
        "sla_deadline": dsr.sla_deadline,
        "message": f"Request received. We will respond within {settings.DSR_RESPONSE_SLA_DAYS} days.",
    }


@router.get("/dsr")
async def list_dsrs(
    status: Optional[DSRStatusEnum] = None,
    assigned_to_me: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """List Data Subject Requests (operator/admin only)."""
    stmt = select(DataSubjectRequest).order_by(desc(DataSubjectRequest.created_at))
    if status:
        stmt = stmt.where(DataSubjectRequest.status == status)
    if assigned_to_me:
        stmt = stmt.where(DataSubjectRequest.assigned_to == current_user.id)

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    dsrs = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "type": d.request_type.value,
            "status": d.status.value,
            "subject_id": d.subject_id,
            "subject_type": d.subject_type,
            "sla_deadline": d.sla_deadline,
            "days_remaining": max(0, (d.sla_deadline - datetime.now(timezone.utc)).days),
            "assigned_to": str(d.assigned_to) if d.assigned_to else None,
            "created_at": d.created_at,
        }
        for d in dsrs
    ]


@router.patch("/dsr/{dsr_id}")
async def update_dsr(
    dsr_id: uuid.UUID,
    payload: DSRUpdateRequest,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Update a DSR status (operator/admin only)."""
    result = await db.execute(select(DataSubjectRequest).where(DataSubjectRequest.id == str(dsr_id)))
    dsr = result.scalar_one_or_none()
    if not dsr:
        raise HTTPException(status_code=404, detail="DSR not found")

    if payload.status:
        dsr.status = payload.status
        if payload.status == DSRStatusEnum.fulfilled:
            dsr.fulfilled_at = datetime.now(timezone.utc)
    if payload.assigned_to:
        dsr.assigned_to = payload.assigned_to
    if payload.fulfillment_notes:
        dsr.fulfillment_notes = payload.fulfillment_notes
    if payload.rejection_reason:
        dsr.rejection_reason = payload.rejection_reason

    await db.commit()
    await db.refresh(dsr)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.dsr_fulfilled if payload.status == DSRStatusEnum.fulfilled else AuditActionEnum.dsr_received,
        actor_id=current_user.id,
        target_type="dsr",
        target_id=dsr.id,
        metadata={"new_status": payload.status.value if payload.status else None},
    )

    return {"id": str(dsr.id), "status": dsr.status.value}


# ─── Breach Notifications ─────────────────────────────────────────────────────

@router.post("/breach", status_code=status.HTTP_201_CREATED)
async def report_breach(
    payload: BreachReportRequest,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Report a data breach. Triggers 72-hour SLA timer."""
    breach = BreachNotification(
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        detected_by=current_user.id,
        affected_subjects_count=payload.affected_subjects_count,
        affected_data_types=payload.affected_data_types or [],
    )
    db.add(breach)
    await db.commit()
    await db.refresh(breach)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.breach_reported,
        actor_id=current_user.id,
        target_type="breach",
        target_id=breach.id,
        metadata={"severity": payload.severity, "affected_count": payload.affected_subjects_count},
    )

    logger.critical("breach_reported", breach_id=str(breach.id), severity=payload.severity)
    return {
        "id": str(breach.id),
        "status": breach.status.value,
        "sla_hours_remaining": settings.BREACH_NOTIFICATION_SLA_HOURS,
        "message": f"Breach reported. Regulator must be notified within {settings.BREACH_NOTIFICATION_SLA_HOURS} hours.",
    }


@router.get("/breach")
async def list_breaches(
    status: Optional[BreachStatusEnum] = None,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """List breach notifications."""
    stmt = select(BreachNotification).order_by(desc(BreachNotification.detected_at))
    if status:
        stmt = stmt.where(BreachNotification.status == status)

    result = await db.execute(stmt)
    breaches = result.scalars().all()

    return [
        {
            "id": str(b.id),
            "title": b.title,
            "severity": b.severity,
            "status": b.status.value,
            "detected_at": b.detected_at,
            "hours_elapsed": round((datetime.now(timezone.utc) - b.detected_at).total_seconds() / 3600, 1),
            "sla_violated": (datetime.now(timezone.utc) - b.detected_at).total_seconds() > settings.BREACH_NOTIFICATION_SLA_HOURS * 3600,
            "affected_subjects_count": b.affected_subjects_count,
        }
        for b in breaches
    ]


@router.patch("/breach/{breach_id}")
async def update_breach(
    breach_id: uuid.UUID,
    payload: BreachUpdateRequest,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Update breach status."""
    result = await db.execute(select(BreachNotification).where(BreachNotification.id == str(breach_id)))
    breach = result.scalar_one_or_none()
    if not breach:
        raise HTTPException(status_code=404, detail="Breach not found")

    breach.status = payload.status
    if payload.containment_measures:
        breach.containment_measures = payload.containment_measures
    if payload.status == BreachStatusEnum.notified_regulator:
        breach.regulator_notified_at = datetime.now(timezone.utc)
    if payload.status == BreachStatusEnum.notified_subjects:
        breach.subjects_notified_at = datetime.now(timezone.utc)
    if payload.status == BreachStatusEnum.resolved:
        breach.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    return {"id": str(breach.id), "status": breach.status.value}


# ─── Conflict of Interest ─────────────────────────────────────────────────────

@router.post("/conflict-of-interest", status_code=status.HTTP_201_CREATED)
async def disclose_conflict(
    payload: COIRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disclose a potential conflict of interest."""
    coi = ConflictOfInterest(
        user_id=current_user.id,
        project_id=payload.project_id,
        relationship_type=payload.relationship_type,
        description=payload.description,
    )
    db.add(coi)
    await db.commit()
    await db.refresh(coi)
    return {
        "id": str(coi.id),
        "disclosed_at": coi.disclosed_at,
        "message": "Disclosure submitted for review",
    }


@router.get("/conflict-of-interest")
async def list_conflicts(
    project_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List conflict of interest disclosures (admin only)."""
    stmt = select(ConflictOfInterest).order_by(desc(ConflictOfInterest.disclosed_at))
    if project_id:
        stmt = stmt.where(ConflictOfInterest.project_id == project_id)

    result = await db.execute(stmt)
    conflicts = result.scalars().all()

    return [
        {
            "id": str(c.id),
            "user_id": str(c.user_id),
            "project_id": str(c.project_id),
            "relationship_type": c.relationship_type,
            "description": c.description,
            "disclosed_at": c.disclosed_at,
            "approved": c.approved,
            "reviewed_by": str(c.reviewed_by) if c.reviewed_by else None,
        }
        for c in conflicts
    ]


@router.post("/conflict-of-interest/{coi_id}/review")
async def review_conflict(
    coi_id: uuid.UUID,
    payload: COIReviewRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Review a conflict of interest disclosure (admin only)."""
    result = await db.execute(select(ConflictOfInterest).where(ConflictOfInterest.id == str(coi_id)))
    coi = result.scalar_one_or_none()
    if not coi:
        raise HTTPException(status_code=404, detail="Disclosure not found")

    coi.approved = payload.approved
    coi.reviewed_by = current_user.id
    coi.review_notes = payload.review_notes
    await db.commit()

    return {
        "id": str(coi.id),
        "approved": payload.approved,
        "review_notes": payload.review_notes,
    }


# ─── Independence Enforcement ─────────────────────────────────────────────────

@router.get("/independence/check/{project_id}")
async def check_independence(
    project_id: uuid.UUID,
    action: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check if a user can perform an action on a project without conflict.

    Blocks PDD drafting requests for ALL roles to maintain independence.
    """
    # Check for undisclosed conflicts
    result = await db.execute(
        select(ConflictOfInterest).where(
            ConflictOfInterest.user_id == current_user.id,
            ConflictOfInterest.project_id == project_id,
            ConflictOfInterest.approved.isnot(True),
        )
    )
    pending_coi = result.scalar_one_or_none()

    if pending_coi:
        return {
            "allowed": False,
            "reason": "Pending conflict of interest disclosure",
            "conflict_id": str(pending_coi.id),
        }

    # Block PDD drafting for independence (ALL roles)
    if "pdd" in action.lower() or "draft" in action.lower():
        return {
            "allowed": False,
            "reason": "PDD drafting is restricted to maintain independence. Please contact an administrator.",
        }

    return {"allowed": True, "reason": None}


# ─── Methodology Versioning ───────────────────────────────────────────────────

@router.post("/methodology", status_code=status.HTTP_201_CREATED)
async def create_methodology_version(
    payload: MethodologyCreateRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new methodology version (admin only)."""
    mv = MethodologyVersion(
        methodology_name=payload.methodology_name,
        version=payload.version,
        effective_date=payload.effective_date,
        rules_json=payload.rules_json,
        change_summary=payload.change_summary,
        approved_by=current_user.id,
    )
    db.add(mv)
    await db.commit()
    await db.refresh(mv)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.methodology_updated,
        actor_id=current_user.id,
        target_type="methodology",
        target_id=mv.id,
        metadata={"name": payload.methodology_name, "version": payload.version},
    )

    return {"id": str(mv.id), "methodology": payload.methodology_name, "version": payload.version}


@router.get("/methodology")
async def list_methodology_versions(
    methodology_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List methodology versions."""
    stmt = select(MethodologyVersion).order_by(desc(MethodologyVersion.effective_date))
    if methodology_name:
        stmt = stmt.where(MethodologyVersion.methodology_name == methodology_name)

    result = await db.execute(stmt)
    versions = result.scalars().all()

    return [
        {
            "id": str(v.id),
            "name": v.methodology_name,
            "version": v.version,
            "effective_date": v.effective_date,
            "is_current": v.is_current,
            "change_summary": v.change_summary,
            "approved_by": str(v.approved_by) if v.approved_by else None,
            "created_at": v.created_at,
        }
        for v in versions
    ]


@router.get("/methodology/current/{methodology_name}")
async def get_current_methodology(
    methodology_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the current version of a methodology."""
    result = await db.execute(
        select(MethodologyVersion)
        .where(
            MethodologyVersion.methodology_name == methodology_name,
            MethodologyVersion.is_current.is_(True),
        )
        .order_by(desc(MethodologyVersion.effective_date))
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Methodology version not found")

    return {
        "id": str(version.id),
        "name": version.methodology_name,
        "version": version.version,
        "effective_date": version.effective_date,
        "rules": version.rules_json,
        "change_summary": version.change_summary,
    }


# ─── Privacy Policy & Terms ───────────────────────────────────────────────────

@router.get("/privacy-policy")
async def privacy_policy():
    """Return the CarbonVerify privacy policy."""
    return {
        "version": "1.0.0",
        "effective_date": "2024-01-01",
        "title": "CarbonVerify Privacy Policy",
        "sections": [
            {
                "heading": "Data Collection",
                "content": "We collect project data, MRV calculations, and contact information necessary for carbon credit verification. Personal data includes email addresses, phone numbers, and GPS coordinates for project locations.",
            },
            {
                "heading": "Data Use",
                "content": "Data is used exclusively for carbon credit MRV preparation, registry submission, and regulatory compliance. We do not sell personal data to third parties.",
            },
            {
                "heading": "Data Retention",
                "content": f"Raw photos are retained for {settings.DATA_RETENTION_YEARS_RAW_PHOTOS} years. Project calculation data is retained for the lifetime of the crediting period plus 7 years for audit purposes.",
            },
            {
                "heading": "Your Rights",
                "content": "Under the Kenya Data Protection Act and GDPR, you have the right to access, rectify, erase, restrict processing, and port your data. Submit requests via POST /compliance/dsr.",
            },
            {
                "heading": "Encryption",
                "content": "Sensitive fields (email, phone numbers, GPS coordinates, household IDs) are encrypted at the application layer using AES-128-GCM. All data in transit uses TLS 1.3.",
            },
            {
                "heading": "Contact",
                "content": "For privacy inquiries: privacy@carbonverify.io",
            },
        ],
    }


@router.get("/terms-of-service")
async def terms_of_service():
    """Return the CarbonVerify terms of service."""
    return {
        "version": "1.0.0",
        "effective_date": "2024-01-01",
        "title": "CarbonVerify Terms of Service",
        "sections": [
            {
                "heading": "Service Description",
                "content": "CarbonVerify provides automated Measurement, Reporting, and Verification (MRV) preparation for carbon credit projects.",
            },
            {
                "heading": "User Obligations",
                "content": "Users must provide accurate data, maintain confidentiality of credentials, and comply with applicable carbon standards (Verra, Gold Standard, Kenya National).",
            },
            {
                "heading": "Limitation of Liability",
                "content": "CarbonVerify is not liable for registry rejection decisions. Final verification and issuance are at the sole discretion of the registry and VVB.",
            },
        ],
    }


# ─── GDPR Erasure (Right to be Forgotten) ─────────────────────────────────────

class ErasureRequest(BaseModel):
    subject_id: str
    subject_type: str  # enumerator | household | developer | user
    reason: Optional[str] = None


@router.post("/erasure", status_code=status.HTTP_202_ACCEPTED)
async def request_erasure(
    payload: ErasureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Initiate GDPR/Kenya DPA right-to-erasure workflow.

    Creates a DSR record and schedules cascading deletion via Celery.
    Actual deletion is async to handle S3, Redis, and audit log cleanup.
    """
    dsr = DataSubjectRequest(
        subject_id=payload.subject_id,
        subject_type=payload.subject_type,
        request_type=DSRTypeEnum.erasure,
        status=DSRStatusEnum.received,
        requested_by=current_user.id,
        details={"reason": payload.reason, "automated": True},
    )
    db.add(dsr)
    await db.commit()
    await db.refresh(dsr)

    # Schedule async erasure task
    from app.tasks.celery_app import celery_app
    celery_app.send_task(
        "app.tasks.compliance.process_erasure_request",
        args=[str(dsr.id)],
    )

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.dsr_received,
        actor_id=current_user.id,
        target_type="dsr",
        target_id=dsr.id,
        metadata={"subject_id": payload.subject_id, "type": "erasure"},
    )

    logger.info(
        "erasure_request_received",
        dsr_id=str(dsr.id),
        subject_id=payload.subject_id,
        subject_type=payload.subject_type,
    )

    return {
        "dsr_id": str(dsr.id),
        "status": "received",
        "message": "Erasure request accepted. Deletion will be processed asynchronously.",
    }
