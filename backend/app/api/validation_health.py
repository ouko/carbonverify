"""Health score history API for continuous validation.

``GET /api/v1/validation/health`` returns the latest snapshot plus the 7-day
history and per-journey pass/fail stats for the last 24 hours. The deploy gate
(``scripts/pre_deploy_check.py``) consumes this endpoint.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_viewer
from app.database import get_db
from app.models import User
from app.validation_engine.health import (
    compute_journey_stats,
    recent_snapshots,
    snapshot_to_dict,
)

router = APIRouter(prefix="/api/v1/validation", tags=["validation-health"])


@router.get("/health")
async def get_validation_health(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
) -> dict[str, Any]:
    """Latest validation health snapshot, 7-day history, and 24h journey stats."""
    history = await recent_snapshots(db)
    snapshots = [snapshot_to_dict(s) for s in history]
    journeys = await compute_journey_stats(db)
    return {
        "latest": snapshots[-1] if snapshots else None,
        "history": snapshots,
        "journeys": journeys,
    }
