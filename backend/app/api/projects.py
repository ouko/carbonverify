from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.database import get_db
from app.models import Project, User, AuditActionEnum, ProjectStatusEnum
from app.security.audit_logging import AuditLogger
from app.schemas import ProjectCreate, ProjectUpdate, ProjectOut
from app.auth.dependencies import require_operator, require_viewer
from app.security.project_auth import require_project_access, get_user_developer_id

router = APIRouter(prefix="/projects", tags=["projects"])


VALID_PROJECT_TRANSITIONS = {
    ProjectStatusEnum.onboarding: {ProjectStatusEnum.data_collection},
    ProjectStatusEnum.data_collection: {ProjectStatusEnum.calculation},
    ProjectStatusEnum.calculation: {ProjectStatusEnum.review},
    ProjectStatusEnum.review: {ProjectStatusEnum.submitted},
    ProjectStatusEnum.submitted: {ProjectStatusEnum.verified},
    ProjectStatusEnum.verified: {ProjectStatusEnum.monitoring},
}


def validate_status_transition(from_status, to_status, valid_map):
    """Validate a status transition against a defined state machine."""
    if from_status == to_status:
        return
    allowed = valid_map.get(from_status, set())
    if to_status not in allowed and to_status.value != "rejected":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {from_status.value} to {to_status.value}",
        )


@router.get("/", response_model=List[ProjectOut])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    stmt = select(Project)
    developer_id = await get_user_developer_id(current_user, db)
    if developer_id:
        stmt = stmt.where(Project.developer_id == developer_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    project = Project(**payload.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_created,
        actor_id=current_user.id,
        target_type="project",
        target_id=project.id,
    )
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    update_data = payload.model_dump(exclude_unset=True)
    if "status" in update_data:
        new_status = ProjectStatusEnum(update_data["status"])
        validate_status_transition(project.status, new_status, VALID_PROJECT_TRANSITIONS)

    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="project",
        target_id=project.id,
    )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    await db.delete(project)
    await db.commit()
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="project",
        target_id=project.id,
        metadata={"event": "project_deleted"},
    )
    return None
