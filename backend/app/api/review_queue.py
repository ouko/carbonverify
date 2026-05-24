from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.database import get_db
from app.models import HumanReviewQueue, User
from app.schemas import HumanReviewQueueCreate, HumanReviewQueueUpdate, HumanReviewQueueOut
from app.auth.dependencies import get_current_user, require_operator, require_viewer

router = APIRouter(prefix="/review-queue", tags=["review-queue"])


@router.get("/", response_model=List[HumanReviewQueueOut])
async def list_queue_items(
    status: str = None,
    assigned_to: uuid.UUID = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(HumanReviewQueue)
    if status:
        stmt = stmt.where(HumanReviewQueue.status == status)
    if assigned_to:
        stmt = stmt.where(HumanReviewQueue.assigned_to == assigned_to)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=HumanReviewQueueOut, status_code=status.HTTP_201_CREATED)
async def create_queue_item(
    payload: HumanReviewQueueCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    item = HumanReviewQueue(**payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/{item_id}", response_model=HumanReviewQueueOut)
async def get_queue_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(HumanReviewQueue).where(HumanReviewQueue.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return item


@router.patch("/{item_id}", response_model=HumanReviewQueueOut)
async def update_queue_item(
    item_id: uuid.UUID,
    payload: HumanReviewQueueUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(HumanReviewQueue).where(HumanReviewQueue.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item
