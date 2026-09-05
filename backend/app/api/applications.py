"""Application intake API routes for the AI-driven application pipeline."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import (
    Application,
    ApplicationDocument,
    User,
)
from app.schemas import (
    ApplicationUpdate,
    ApplicationOut,
    ApplicationDocumentOut,
    ApplicationIntakeRequest,
)
from app.auth.dependencies import require_viewer, require_operator, require_admin
from app.services.application_tokens import create_applicant_token
from app.core.encryption import compute_searchable_hash
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])


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
    response_data = ApplicationOut.model_validate(application).model_dump()
    response_data["applicant_token"] = token
    return response_data


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


@router.post("/{application_id}/trigger-pipeline", response_model=ApplicationOut)
async def trigger_application_pipeline(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Trigger the ai_application_pipeline validation workflow for an application."""
    result = await db.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Placeholder for Phase 2: actually create/run ValidationRun
    logger.info("pipeline_triggered", application_id=str(application_id))
    return application
