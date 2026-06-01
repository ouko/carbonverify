import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models import Project, FileUpload, FileUploadStatusEnum, User, AuditActionEnum
from app.security.audit_logging import AuditLogger
from app.schemas import FileUploadOut, FileUploadResponse
from app.auth.dependencies import require_operator, require_viewer
from app.services.file_detector import detect_file_type, compute_sha256, generate_s3_key
from app.services.s3 import upload_bytes
from app.services.provenance import build_full_provenance
from app.tasks.jobs import process_uploaded_file
from app.services.clamav_scanner import get_scanner, ScanStatus
from app.core.logging import get_logger
from app.config import get_settings

logger = get_logger(__name__)
router = APIRouter(prefix="/uploads", tags=["uploads"])
limiter = Limiter(key_func=get_remote_address)
settings = get_settings()

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@limiter.limit("30/minute")
@router.post("/projects/{project_id}/upload", response_model=FileUploadResponse)
async def upload_file(
    project_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    source_type: str = Form("document"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    # Validate project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not settings.S3_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="S3 bucket not configured")

    # Validate filename extension
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file bytes
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE / 1024 / 1024}MB")

    # Detect file type by magic bytes
    detected_type, mime_type = detect_file_type(file_bytes)
    if detected_type.value == "unknown":
        logger.warning("unknown_file_type", filename=filename, ext=ext)
        # Fall back to extension-based detection
        if ext in (".xlsx", ".xls"):
            detected_type_str = "excel"
        elif ext == ".csv":
            detected_type_str = "csv"
        elif ext == ".pdf":
            detected_type_str = "pdf"
        elif ext in (".jpg", ".jpeg", ".png", ".webp"):
            detected_type_str = "image"
        else:
            raise HTTPException(status_code=400, detail="Could not determine file type")
    else:
        detected_type_str = detected_type.value

    # Virus scan
    scanner = get_scanner()
    scan_result = await scanner.scan_buffer(file_bytes)
    if scan_result.status == ScanStatus.infected:
        logger.warning("upload_rejected_malware", filename=filename, signature=scan_result.signature)
        raise HTTPException(status_code=400, detail=f"File rejected: malware detected ({scan_result.signature})")

    # Compute hash
    file_hash = compute_sha256(file_bytes)

    # Generate S3 key and upload
    s3_key = generate_s3_key(str(project_id), source_type, filename)
    try:
        upload_bytes(file_bytes, s3_key, content_type=mime_type)
    except Exception as e:
        logger.error("s3_upload_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to upload file to storage")

    # Create database record
    upload_record = FileUpload(
        project_id=project_id,
        original_filename=filename,
        detected_type=detected_type,
        mime_type=mime_type,
        s3_key=s3_key,
        s3_bucket=settings.S3_BUCKET_NAME,
        file_size_bytes=len(file_bytes),
        file_hash_sha256=file_hash,
        status=FileUploadStatusEnum.uploaded,
        provenance=build_full_provenance(
            file_bytes=file_bytes,
            original_filename=filename,
            detected_type=detected_type_str,
            s3_key=s3_key,
        ),
    )
    db.add(upload_record)
    await db.commit()
    await db.refresh(upload_record)

    # Queue async processing
    process_uploaded_file.delay(str(upload_record.id))

    logger.info(
        "file_uploaded",
        upload_id=str(upload_record.id),
        project_id=str(project_id),
        detected_type=detected_type_str,
        user_id=str(current_user.id),
    )

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.data_ingested,
        actor_id=current_user.id,
        target_type="file_upload",
        target_id=upload_record.id,
        metadata={"project_id": str(project_id), "detected_type": detected_type_str, "filename": filename},
        request=request,
    )

    return FileUploadResponse(
        file_id=upload_record.id,
        detected_type=detected_type_str,
        mime_type=mime_type,
        status=upload_record.status.value,
        s3_key=s3_key,
        file_size_bytes=len(file_bytes),
        file_hash_sha256=file_hash,
        message="File uploaded successfully. Processing queued.",
    )


@router.get("/projects/{project_id}/uploads", response_model=List[FileUploadOut])
async def list_project_uploads(
    project_id: uuid.UUID,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(FileUpload).where(FileUpload.project_id == project_id)
    if status:
        stmt = stmt.where(FileUpload.status == status)
    stmt = stmt.order_by(FileUpload.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{upload_id}", response_model=FileUploadOut)
async def get_upload(
    upload_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(FileUpload).where(FileUpload.id == upload_id))
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    return upload


@limiter.limit("30/minute")
@router.post("/{upload_id}/reprocess", response_model=FileUploadResponse)
async def reprocess_upload(
    upload_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(FileUpload).where(FileUpload.id == upload_id))
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload.status = FileUploadStatusEnum.processing
    await db.commit()

    process_uploaded_file.delay(str(upload.id))

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.data_ingested,
        actor_id=_.id,
        target_type="file_upload",
        target_id=upload.id,
        metadata={"event": "reprocess", "project_id": str(upload.project_id)},
        request=request,
    )

    return FileUploadResponse(
        file_id=upload.id,
        detected_type=upload.detected_type.value,
        mime_type=upload.mime_type,
        status=upload.status.value,
        s3_key=upload.s3_key,
        file_size_bytes=upload.file_size_bytes,
        file_hash_sha256=upload.file_hash_sha256,
        message="Reprocessing queued.",
    )
