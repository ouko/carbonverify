from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import User
from app.schemas import UserOut
from pydantic import BaseModel

class UserSettingsUpdate(BaseModel):
    # Legacy fields
    email_notifications: bool | None = None
    push_notifications: bool | None = None
    sms_notifications: bool | None = None
    auto_assign_queue: bool | None = None
    confidence_threshold: float | None = None
    theme: str | None = None
    # Frontend preference fields
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
from app.auth.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/", response_model=List[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User))
    return result.scalars().all()


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
