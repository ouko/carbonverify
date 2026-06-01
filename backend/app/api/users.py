from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models import User, RefreshToken, AuditActionEnum
from app.schemas import (
    UserOut, UserDetailOut, UserCreateByAdmin, UserUpdateByAdmin,
    PermissionGrantRequest, PermissionRevokeRequest, SessionOut,
)
from app.auth.dependencies import get_current_user, require_admin, require_permission
from app.auth.security import get_password_hash
from app.auth.sessions import SessionManager
from app.permissions import list_all_permissions, has_permission
from app.security.audit_logging import AuditLogger
from app.core.logging import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


class UserSettingsUpdate(BaseModel):
    email_notifications: bool | None = None
    push_notifications: bool | None = None
    sms_notifications: bool | None = None
    auto_assign_queue: bool | None = None
    confidence_threshold: float | None = None
    theme: str | None = None
    notifyHumanReview: bool | None = None
    notifyVVB: bool | None = None
    notifyAnomaly: bool | None = None
    notifyChurn: bool | None = None
    notifyDeadline: bool | None = None
    channelEmail: bool | None = None
    channelInApp: bool | None = None
    channelSMS: bool | None = None
    channelWhatsApp: bool | None = None
    digestMode: str | None = None
    autoAssign: bool | None = None
    autoAdvanceThreshold: float | None = None


# ─── Self-service endpoints ───────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/settings")
async def get_user_settings(
    current_user: User = Depends(get_current_user),
):
    """Get the current user's settings/preferences."""
    return {"settings": current_user.settings or {}}


@router.put("/me/settings")
async def update_user_settings(
    payload: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's settings/preferences."""
    update_data = payload.model_dump(exclude_unset=True)
    if current_user.settings is None:
        current_user.settings = {}
    current_user.settings.update(update_data)
    await db.commit()
    await db.refresh(current_user)
    return {"settings": current_user.settings}


# ─── Admin endpoints ──────────────────────────────────────────────────────────

@router.get("/", response_model=List[UserOut])
async def list_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
):
    """List all users with optional filtering."""
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if search:
        # Defensive: limit search length, sanitize wildcards
        search_clean = search[:100].replace("%", "\\%").replace("_", "\\_")
        pattern = "%" + search_clean + "%"
        stmt = stmt.where(User.name.ilike(pattern) | User.email.ilike(pattern))
    stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateByAdmin,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:create")),
):
    """Create a new user (admin only)."""
    from app.core.encryption import compute_searchable_hash

    email_hash = compute_searchable_hash(payload.email)
    result = await db.execute(select(User).where(User.email_hash == email_hash))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        email_hash=email_hash,
        name=payload.name,
        role=payload.role,
        mfa_enabled=payload.mfa_enabled,
        hashed_password=get_password_hash(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_created,
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "admin_user_creation", "created_by": str(current_user.id)},
    )

    logger.info("admin_created_user", admin_id=str(current_user.id), user_id=str(user.id))
    return user


@router.get("/{user_id}", response_model=UserDetailOut)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
):
    """Get detailed user information."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateByAdmin,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:update")),
):
    """Update a user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deactivation
    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    update_data = payload.model_dump(exclude_unset=True)

    if "role" in update_data:
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        from app.permissions import has_permission
        if not has_permission(current_user.role.value, current_user.permissions or [], "users:manage_roles"):
            raise HTTPException(status_code=403, detail="Permission denied: users:manage_roles")

    # If email is being updated, recompute hash and check uniqueness
    if "email" in update_data:
        from app.core.encryption import compute_searchable_hash
        new_hash = compute_searchable_hash(update_data["email"])
        existing = await db.execute(select(User).where(User.email_hash == new_hash, User.id != user_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email_hash = new_hash

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "admin_user_update", "updated_by": str(current_user.id), "changes": list(update_data.keys())},
    )

    logger.info("admin_updated_user", admin_id=str(current_user.id), user_id=str(user.id))
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:delete")),
):
    """Soft-delete (deactivate) a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    user.is_active = False
    await db.commit()

    # Revoke all sessions and refresh tokens
    await SessionManager.destroy_all_user_sessions(str(user.id))
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "admin_user_deactivation"},
    )

    logger.info("admin_deactivated_user", admin_id=str(current_user.id), user_id=str(user.id))
    return None


@router.post("/{user_id}/reactivate", response_model=UserOut)
async def reactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:update")),
):
    """Reactivate a deactivated user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    user.failed_login_count = 0
    user.locked_until = None
    user.password_reset_required = True
    await db.commit()
    await db.refresh(user)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "admin_user_reactivation"},
    )

    logger.info("admin_reactivated_user", admin_id=str(current_user.id), user_id=str(user.id))
    return user


@router.get("/{user_id}/permissions", response_model=List[str])
async def get_user_permissions(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
):
    """Get effective permissions for a user (role + explicit)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from app.permissions import get_permissions_for_role
    role_perms = get_permissions_for_role(user.role.value)
    explicit_perms = set(user.permissions or [])
    return sorted(role_perms | explicit_perms)


@router.post("/{user_id}/permissions", response_model=List[str])
async def grant_permission(
    user_id: uuid.UUID,
    payload: PermissionGrantRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage_permissions")),
):
    """Grant an explicit permission to a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    all_perms = list_all_permissions()
    if payload.permission not in all_perms:
        raise HTTPException(status_code=400, detail=f"Unknown permission: {payload.permission}")

    from app.permissions import has_permission
    if not has_permission(current_user.role.value, current_user.permissions or [], payload.permission):
        raise HTTPException(status_code=403, detail="You cannot grant a permission you do not possess")

    perms = list(user.permissions or [])
    if payload.permission not in perms:
        perms.append(payload.permission)
        user.permissions = perms
        await db.commit()
        await db.refresh(user)

    logger.info("admin_granted_permission", admin_id=str(current_user.id), user_id=str(user.id), permission=payload.permission)
    return sorted(perms)


@router.delete("/{user_id}/permissions/{permission}", response_model=List[str])
async def revoke_permission(
    user_id: uuid.UUID,
    permission: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage_permissions")),
):
    """Revoke an explicit permission from a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    perms = list(user.permissions or [])
    if permission in perms:
        perms.remove(permission)
        user.permissions = perms
        await db.commit()
        await db.refresh(user)

    logger.info("admin_revoked_permission", admin_id=str(current_user.id), user_id=str(user.id), permission=permission)
    return sorted(perms)


@router.get("/{user_id}/sessions", response_model=List[SessionOut])
async def get_user_sessions(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    request: Optional[object] = None,
    _: User = Depends(require_permission("users:manage_sessions")),
):
    """List active sessions for a specific user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sessions = await SessionManager.list_user_sessions(str(user_id))
    return [
        SessionOut(
            id=s["session_id"],
            user_id=str(user_id),
            user_name=user.name,
            user_email=user.email,
            device=s.get("user_agent", "Unknown device"),
            ip=s.get("ip_address", "unknown"),
            last_active=s.get("last_activity_at"),
            created_at=s.get("created_at"),
        )
        for s in sessions
    ]


@router.delete("/{user_id}/sessions/{session_id}")
async def revoke_user_session(
    user_id: uuid.UUID,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage_sessions")),
):
    """Revoke a specific session for a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await SessionManager.destroy_session(session_id)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_logout,
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "admin_session_revoke", "session_id": session_id},
    )

    logger.info("admin_revoked_session", admin_id=str(current_user.id), user_id=str(user.id), session_id=session_id)
    return {"message": "Session revoked"}


@router.post("/{user_id}/logout-all")
async def force_logout_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage_sessions")),
):
    """Force logout a user from all devices."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await SessionManager.destroy_all_user_sessions(str(user_id))
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_logout,
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "admin_force_logout"},
    )

    logger.info("admin_force_logout", admin_id=str(current_user.id), user_id=str(user.id))
    return {"message": "All sessions terminated for user"}
