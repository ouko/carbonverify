from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.database import get_db
from app.models import DataSource, User, AuditActionEnum
from app.security.audit_logging import AuditLogger
from app.schemas import DataSourceCreate, DataSourceUpdate, DataSourceOut
from app.auth.dependencies import require_operator, require_viewer

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


@router.get("/", response_model=List[DataSourceOut])
async def list_data_sources(
    project_id: uuid.UUID = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(DataSource)
    if project_id:
        stmt = stmt.where(DataSource.project_id == project_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=DataSourceOut, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    payload: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    ds = DataSource(**payload.model_dump())
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.data_ingested,
        actor_id=current_user.id,
        target_type="data_source",
        target_id=ds.id,
    )
    return ds


@router.get("/{ds_id}", response_model=DataSourceOut)
async def get_data_source(
    ds_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    return ds


@router.patch("/{ds_id}", response_model=DataSourceOut)
async def update_data_source(
    ds_id: uuid.UUID,
    payload: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ds, field, value)
    await db.commit()
    await db.refresh(ds)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="data_source",
        target_id=ds.id,
    )
    return ds


@router.delete("/{ds_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(
    ds_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    await db.delete(ds)
    await db.commit()
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="data_source",
        target_id=ds.id,
        metadata={"event": "data_source_deleted"},
    )
    return None
