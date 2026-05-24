from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.database import get_db
from app.models import DataSource, User
from app.schemas import DataSourceCreate, DataSourceUpdate, DataSourceOut
from app.auth.dependencies import get_current_user, require_operator, require_viewer

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


@router.get("/", response_model=List[DataSourceOut])
async def list_data_sources(
    project_id: uuid.UUID = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(DataSource)
    if project_id:
        stmt = stmt.where(DataSource.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=DataSourceOut, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    payload: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    ds = DataSource(**payload.model_dump())
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
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
    _: User = Depends(require_operator),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ds, field, value)
    await db.commit()
    await db.refresh(ds)
    return ds
