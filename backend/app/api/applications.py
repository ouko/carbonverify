"""Application intake API routes for the AI-driven application pipeline."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import (
    Application,
    ApplicationDocument,
    ApplicationDocumentSourceEnum,
    ApplicationDocumentStatusEnum,
    User,
)
from app.schemas import (
    ApplicationUpdate,
    ApplicationOut,
    ApplicationDocumentOut,
    ApplicationIntakeRequest,
)
from app.auth.dependencies import require_viewer, require_operator, require_admin
from app.services.application_tokens import create_applicant_token, verify_applicant_token
from app.services.application_pipeline import ensure_default_application_pipeline
from app.core.encryption import compute_searchable_hash
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


async def get_current_applicant(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> Application:
    """Authenticate an applicant via their bearer token and return the application."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing applicant token")
    token = authorization.split(" ", 1)[1].strip()
    token_app_id = verify_applicant_token(token)
    if token_app_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired applicant token")
    if token_app_id != application_id:
        raise HTTPException(status_code=403, detail="Token does not match this application")
    result = await db.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationIntakeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint for project owners to submit an intake application."""
    email_hash = compute_searchable_hash(payload.applicant_email)
    application = Application(
        applicant_email_hash=email_hash,
        applicant_email_encrypted=payload.applicant_email,
        organization_name=payload.organization_name,
        project_title=payload.project_title,
        country=payload.country,
        sector=payload.sector,
        proposed_methodology=payload.proposed_methodology,
        status="intake",
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)

    token = create_applicant_token(application.id)
    await _send_applicant_welcome_email(payload.applicant_email, application, token)
    response_data = ApplicationOut.model_validate(application).model_dump()
    response_data["applicant_token"] = token
    return response_data


async def _send_applicant_welcome_email(email: str, application: Application, token: str) -> None:
    """Best-effort welcome email with the secure applicant portal link."""
    try:
        from app.config import get_settings
        from app.services.email import get_email_service

        frontend_url = get_settings().FRONTEND_URL or ""
        portal_url = (
            f"{frontend_url}/apply/portal"
            f"?application_id={application.id}&token={token}"
        )
        await get_email_service().send_email(
            to=email,
            subject="Your CarbonVerify application — next steps",
            body_text=(
                f"Hi,\n\n"
                f"Your application '{application.project_title}' has been received.\n\n"
                f"Use your secure portal link to upload documents and track progress:\n"
                f"{portal_url}\n\n"
                f"The link is valid for 7 days.\n\n"
                f"— CarbonVerify"
            ),
        )
        logger.info("applicant_welcome_email_sent", application_id=str(application.id))
    except Exception as exc:
        # Email is best-effort — never fail intake because of it
        logger.warning("applicant_welcome_email_failed", application_id=str(application.id), error=str(exc))


@router.get("", response_model=List[ApplicationOut])
async def list_applications(
    status: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Application)
    if status:
        stmt = stmt.where(Application.status == status)
    if country:
        stmt = stmt.where(Application.country.ilike(f"%{country}%"))
    if sector:
        stmt = stmt.where(Application.sector == sector)
    stmt = stmt.order_by(Application.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.patch("/{application_id}", response_model=ApplicationOut)
async def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(application, key, value)

    await db.commit()
    await db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    await db.delete(application)
    await db.commit()


@router.get("/{application_id}/documents", response_model=List[ApplicationDocumentOut])
async def list_application_documents(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(ApplicationDocument).where(ApplicationDocument.application_id == application_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/{application_id}/documents",
    response_model=ApplicationDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_application_document(
    application_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    application: Application = Depends(get_current_applicant),
):
    """Applicant-facing document upload (authenticated with the applicant token).

    Virus-scans the file, stores it in S3, extracts text, and records the
    document against the application for the AI classification step.
    """
    from app.config import get_settings
    from app.services.clamav_scanner import get_scanner, ScanStatus
    from app.services.file_detector import compute_sha256, generate_s3_key
    from app.services.lead_intelligence.document_text import extract_text_async
    from app.services.s3 import upload_bytes

    settings = get_settings()
    if not settings.S3_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="Storage not configured")

    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size: 50MB")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    scanner = get_scanner()
    scan_result = await scanner.scan_buffer(file_bytes)
    if scan_result.status == ScanStatus.infected:
        logger.warning(
            "applicant_upload_rejected_malware",
            application_id=str(application_id),
            filename=filename,
            signature=scan_result.signature,
        )
        raise HTTPException(status_code=400, detail=f"File rejected: malware detected ({scan_result.signature})")
    if scan_result.status == ScanStatus.error:
        logger.error(
            "applicant_upload_scan_error",
            application_id=str(application_id),
            filename=filename,
            message=scan_result.message,
        )
        raise HTTPException(status_code=503, detail="Virus scanner unavailable; upload rejected for safety")

    file_hash = compute_sha256(file_bytes)
    mime_type = file.content_type or "application/octet-stream"
    s3_key = generate_s3_key(str(application_id), "application_document", filename)
    try:
        upload_bytes(file_bytes, s3_key, content_type=mime_type)
    except Exception as exc:
        logger.error("applicant_upload_s3_failed", application_id=str(application_id), error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to store file")

    try:
        extracted_text = await extract_text_async(file_bytes, mime_type) or None
    except Exception as exc:
        logger.warning("applicant_upload_text_extraction_failed", filename=filename, error=str(exc))
        extracted_text = None

    document = ApplicationDocument(
        application_id=application_id,
        source_type=ApplicationDocumentSourceEnum.upload,
        s3_key=s3_key,
        original_filename=filename,
        mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        file_hash_sha256=file_hash,
        status=ApplicationDocumentStatusEnum.fetched,
        extracted_text=extracted_text,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    logger.info(
        "applicant_document_uploaded",
        application_id=str(application_id),
        document_id=str(document.id),
        filename=filename,
    )
    return document


@router.get("/{application_id}/portal")
async def applicant_portal(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    application: Application = Depends(get_current_applicant),
):
    """Applicant-facing status view: application state, documents, and gap findings."""
    stmt = select(ApplicationDocument).where(ApplicationDocument.application_id == application_id)
    stmt = stmt.order_by(ApplicationDocument.created_at.desc())
    result = await db.execute(stmt)
    documents = result.scalars().all()
    return {
        "application_id": str(application.id),
        "project_title": application.project_title,
        "status": application.status.value,
        "gap_findings": application.gap_findings or {},
        "documents": [ApplicationDocumentOut.model_validate(d).model_dump(mode="json") for d in documents],
    }


@router.post("/{application_id}/trigger-pipeline", response_model=ApplicationOut)
async def trigger_application_pipeline(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Create a ValidationRun against the ai_application_pipeline template and queue it.

    The Celery worker executes intake (binds the existing application) →
    document collection → AI classification with gap analysis.
    """
    from app.validation_engine.orchestrator import ValidationOrchestrator
    from app.validation_engine.tasks import execute_validation_run

    result = await db.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    workflow = await ensure_default_application_pipeline(db)
    orchestrator = ValidationOrchestrator(db)
    run = await orchestrator.create_run(
        workflow_id=str(workflow.id),
        trigger_event="application_pipeline",
        input_data={
            "application_id": str(application.id),
            "applicant_email": application.applicant_email_encrypted or "",
            "organization_name": application.organization_name,
            "project_title": application.project_title,
            "country": application.country,
            "sector": application.sector,
            "proposed_methodology": application.proposed_methodology,
        },
    )
    application.validation_run_id = run.id
    await db.commit()

    execute_validation_run.delay(str(run.id))
    logger.info(
        "application_pipeline_triggered",
        application_id=str(application_id),
        run_id=str(run.id),
    )
    return application
