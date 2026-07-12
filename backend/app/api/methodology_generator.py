"""API for AI-generated custom carbon credit methodologies."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import GeneratedMethodology, User, AuditActionEnum
from app.schemas import (
    GeneratedMethodologyCreate,
    GeneratedMethodologyOut,
    GeneratedMethodologyStatusUpdate,
)
from app.auth.dependencies import get_current_user, require_operator
from app.security.audit_logging import AuditLogger
from app.services.methodology_generator import MethodologyGeneratorService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/methodology-generator", tags=["methodology-generator"])

VALID_STATUS_TRANSITIONS = {
    "draft": {"under_review"},
    "under_review": {"approved", "rejected", "revision_requested"},
    "revision_requested": {"draft"},
}


def _to_dict(gm: GeneratedMethodology) -> Dict[str, Any]:
    return {
        "id": gm.id,
        "project_id": gm.project_id,
        "name": gm.name,
        "sector": gm.sector,
        "activity_description": gm.activity_description,
        "boundaries": gm.boundaries_json,
        "data_sources": gm.data_sources_json,
        "gap_analysis": gm.gap_analysis_json,
        "methodology": gm.methodology_json,
        "quantification_scaffold": gm.quantification_scaffold_json,
        "status": gm.status,
        "rejection_reason": gm.rejection_reason,
        "reviewed_by": gm.reviewed_by,
        "reviewed_at": gm.reviewed_at,
        "created_by": gm.created_by,
        "created_at": gm.created_at,
        "updated_at": gm.updated_at,
    }


@router.post("/", response_model=GeneratedMethodologyOut, status_code=status.HTTP_201_CREATED)
async def create_generated_methodology(
    payload: GeneratedMethodologyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gm = GeneratedMethodology(
        project_id=payload.project_id,
        name=payload.name,
        sector=payload.sector,
        activity_description=payload.activity_description,
        boundaries_json=payload.boundaries,
        data_sources_json=payload.data_sources,
        created_by=current_user.id,
    )
    db.add(gm)
    await db.commit()
    await db.refresh(gm)
    logger.info("generated_methodology_created", id=str(gm.id), user_id=str(current_user.id))
    return _to_dict(gm)


@router.get("/", response_model=List[GeneratedMethodologyOut])
async def list_generated_methodologies(
    project_id: uuid.UUID = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GeneratedMethodology).order_by(desc(GeneratedMethodology.created_at))
    if project_id:
        stmt = stmt.where(GeneratedMethodology.project_id == project_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return [_to_dict(gm) for gm in result.scalars().all()]


@router.get("/{methodology_id}", response_model=GeneratedMethodologyOut)
async def get_generated_methodology(
    methodology_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GeneratedMethodology).where(GeneratedMethodology.id == methodology_id)
    )
    gm = result.scalar_one_or_none()
    if not gm:
        raise HTTPException(status_code=404, detail="Generated methodology not found")
    return _to_dict(gm)


@router.post("/{methodology_id}/analyze")
async def analyze_methodology_fit(
    methodology_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GeneratedMethodology).where(GeneratedMethodology.id == methodology_id)
    )
    gm = result.scalar_one_or_none()
    if not gm:
        raise HTTPException(status_code=404, detail="Generated methodology not found")

    service = MethodologyGeneratorService()
    existing = await service.fetch_existing_methodologies(db)
    project_context = {
        "name": gm.name,
        "sector": gm.sector,
        "activity_description": gm.activity_description,
        "boundaries": gm.boundaries_json,
        "data_sources": gm.data_sources_json,
    }
    gap_analysis = await service.analyze_gap(project_context, existing)
    gm.gap_analysis_json = gap_analysis
    await db.commit()
    await db.refresh(gm)
    return _to_dict(gm)


@router.post("/{methodology_id}/generate")
async def generate_methodology_draft(
    methodology_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GeneratedMethodology).where(GeneratedMethodology.id == methodology_id)
    )
    gm = result.scalar_one_or_none()
    if not gm:
        raise HTTPException(status_code=404, detail="Generated methodology not found")
    if not gm.gap_analysis_json:
        raise HTTPException(status_code=400, detail="Run gap analysis first")
    if gm.gap_analysis_json.get("fits_existing_methodology"):
        raise HTTPException(
            status_code=400,
            detail="Project appears to fit an existing methodology; generation blocked.",
        )

    service = MethodologyGeneratorService()
    project_context = {
        "name": gm.name,
        "sector": gm.sector,
        "activity_description": gm.activity_description,
        "boundaries": gm.boundaries_json,
        "data_sources": gm.data_sources_json,
    }
    generated = await service.generate_methodology(project_context, gm.gap_analysis_json)
    gm.methodology_json = generated["methodology"]
    gm.quantification_scaffold_json = generated["quantification_scaffold"]
    await db.commit()
    await db.refresh(gm)
    return _to_dict(gm)


@router.patch("/{methodology_id}/status", response_model=GeneratedMethodologyOut)
async def update_methodology_status(
    methodology_id: uuid.UUID,
    payload: GeneratedMethodologyStatusUpdate,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GeneratedMethodology).where(GeneratedMethodology.id == methodology_id)
    )
    gm = result.scalar_one_or_none()
    if not gm:
        raise HTTPException(status_code=404, detail="Generated methodology not found")

    current = gm.status
    target = payload.status
    allowed = VALID_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {current} to {target}",
        )

    gm.status = target
    if target in {"rejected", "revision_requested"}:
        if not payload.rejection_reason:
            raise HTTPException(status_code=400, detail="Rejection reason required")
        gm.rejection_reason = payload.rejection_reason
    if target in {"approved", "rejected", "revision_requested"}:
        gm.reviewed_by = current_user.id
        gm.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(gm)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.methodology_updated,
        actor_id=current_user.id,
        target_type="generated_methodology",
        target_id=gm.id,
        metadata={"previous_status": current, "new_status": target},
    )
    return _to_dict(gm)


@router.post("/{methodology_id}/export")
async def export_methodology(
    methodology_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GeneratedMethodology).where(GeneratedMethodology.id == methodology_id)
    )
    gm = result.scalar_one_or_none()
    if not gm or not gm.methodology_json:
        raise HTTPException(status_code=404, detail="Generated methodology draft not found")

    sections = []
    for key, value in gm.methodology_json.items():
        title = key.replace("_", " ").title()
        body = value if isinstance(value, str) else json.dumps(value, indent=2)
        sections.append(f"## {title}\n\n{body}\n")

    markdown = f"""# {gm.name}\n\n**Sector:** {gm.sector}  \n**Status:** {gm.status}  \n\n{''.join(sections)}"""
    return {"format": "markdown", "content": markdown}
