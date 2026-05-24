"""
Project-level authorization for CarbonVerify.

Ensures developers can only access their own projects,
and implements field-level access control.
"""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, UserRoleEnum, Project, Developer
from app.auth.dependencies import get_current_user


class ProjectAccessError(HTTPException):
    def __init__(self, detail: str = "Access denied to this project"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


async def require_project_access(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """
    Verify the current user has access to a specific project.

    Rules:
        - Admin: all projects
        - Operator: all projects
        - Developer: only their own projects
        - Viewer: only their own projects (if assigned)
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Admins and operators have universal access
    if current_user.role in (UserRoleEnum.admin, UserRoleEnum.operator):
        return project

    # Developers and viewers can only access their own projects
    if current_user.role in (UserRoleEnum.developer, UserRoleEnum.viewer):
        result = await db.execute(
            select(Developer).where(Developer.user_id == current_user.id)
        )
        developer = result.scalar_one_or_none()

        if not developer:
            raise ProjectAccessError("User is not associated with a developer profile")

        if project.developer_id != developer.id:
            raise ProjectAccessError("You can only access your own projects")

        return project

    raise ProjectAccessError()


async def can_modify_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """
    Verify user can modify a project.

    Only admin, operator, and the project's developer can modify.
    Viewers have read-only access.
    """
    project = await require_project_access(project_id, current_user, db)

    if current_user.role == UserRoleEnum.viewer:
        raise HTTPException(status_code=403, detail="Viewers have read-only access")

    return project


def filter_projects_for_user(
    projects: list[Project],
    current_user: User,
    developer_id: Optional[uuid.UUID] = None,
) -> list[Project]:
    """
    Filter a list of projects to only those accessible by the user.
    """
    if current_user.role in (UserRoleEnum.admin, UserRoleEnum.operator):
        return projects

    if developer_id:
        return [p for p in projects if p.developer_id == developer_id]

    return []


async def get_user_developer_id(
    user: User,
    db: AsyncSession,
) -> Optional[uuid.UUID]:
    """Get the developer ID associated with a user, if any."""
    if user.role not in (UserRoleEnum.developer, UserRoleEnum.viewer):
        return None

    result = await db.execute(select(Developer).where(Developer.user_id == user.id))
    developer = result.scalar_one_or_none()
    return developer.id if developer else None
