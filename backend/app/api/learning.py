"""Agent learning loop API: calibration, weekly reports, recent overrides.

Mounted at ``/api/v1/learning``. All endpoints require operator (or above).

Route ordering: static routes (``/calibration``, ``/report/weekly/generate``)
are declared before parameterized ones.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_operator
from app.database import get_db
from app.learning.models import LearningReport
from app.learning.service import LearningLoopService

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])


@router.get("/calibration")
async def get_calibration(
    days: int = Query(30, ge=1, le=365),
    current_user=Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Per-agent override calibration statistics."""
    service = LearningLoopService(db)
    return await service.compute_calibration(days=days)


@router.post("/report/weekly/generate", status_code=201)
async def generate_weekly_report(
    current_user=Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Run the weekly retraining report and persist it."""
    service = LearningLoopService(db)
    return await service.weekly_retraining_report(persist=True)


@router.get("/report/weekly")
async def get_latest_weekly_report(
    current_user=Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the most recently stored weekly retraining report."""
    result = await db.execute(
        select(LearningReport)
        .where(LearningReport.report_type == "weekly_retraining")
        .order_by(LearningReport.created_at.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="No weekly report generated yet")
    return {
        "id": str(report.id),
        "report_type": report.report_type,
        "report": report.report,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/overrides")
async def get_recent_overrides(
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Recent human overrides paired with the agent decisions they reversed."""
    service = LearningLoopService(db)
    return {"overrides": await service.recent_overrides(limit=limit)}


__all__ = ["router"]
