"""Read-only API for methodology starting templates."""

import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import MethodologyTemplateOut
from app.auth.dependencies import get_current_user
from app.services.methodology_generator import MethodologyTemplateService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/methodology-templates", tags=["methodology-templates"])
service = MethodologyTemplateService()


def _template_to_dict(template) -> Dict[str, Any]:
    safe_defaults = service.defaults_to_form(template)
    return {
        "id": template.id,
        "name": template.name,
        "sector": template.sector,
        "is_active": template.is_active,
        "defaults_json": {
            "boundaries": safe_defaults["boundaries"],
            "data_sources": safe_defaults["data_sources"],
        },
        "description": template.description,
        "created_by": template.created_by,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


@router.get("/", response_model=List[MethodologyTemplateOut])
async def list_methodology_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    templates = await service.list_active(db)
    logger.info("methodology_templates_listed", count=len(templates), user_id=str(current_user.id))
    return [_template_to_dict(t) for t in templates]


@router.get("/{template_id}", response_model=MethodologyTemplateOut)
async def get_methodology_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    template = await service.get(db, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return _template_to_dict(template)
