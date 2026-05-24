from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict

from app.database import get_db
from app.models import Project, CalculationRun, HumanReviewQueue, User
from app.schemas import DashboardStats
from app.auth.dependencies import get_current_user, require_viewer

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    total_projects = await db.scalar(select(func.count(Project.id)))

    status_counts = {}
    for status in ["onboarding", "data_collection", "calculation", "review", "submitted", "verified", "monitoring"]:
        count = await db.scalar(select(func.count(Project.id)).where(Project.status == status))
        status_counts[status] = count or 0

    pending_reviews = await db.scalar(
        select(func.count(HumanReviewQueue.id)).where(HumanReviewQueue.status.in_(["pending", "in_review"]))
    )

    recent_calculations = await db.scalar(select(func.count(CalculationRun.id)))

    total_emissions = await db.scalar(
        select(func.coalesce(func.sum(CalculationRun.emissions_reduction_tCO2e), 0.0)).where(
            CalculationRun.status == "approved"
        )
    )

    return DashboardStats(
        total_projects=total_projects or 0,
        projects_by_status=status_counts,
        pending_reviews=pending_reviews or 0,
        recent_calculations=recent_calculations or 0,
        total_emissions_reduced=total_emissions or 0.0,
    )
