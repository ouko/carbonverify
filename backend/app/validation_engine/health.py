"""Composite health-score computation and snapshot storage for continuous validation.

Pure scoring functions (``compute_*``) are importable and unit-testable without
a database; ``compute_and_store_snapshot`` collects the underlying statistics
and appends a ``validation_health_snapshots`` row.

Score formula (0-100, higher is healthier):

- Synthetic journey success rate (last 24h) — weight 60%
- Remediation resolution rate (shared remediation engine attempts) — weight 20%
- Escalation backlog (open escalation events) — weight 20%

Snapshots below ``HEALTH_THRESHOLD`` (90) increment ``consecutive_below_threshold``;
a snapshot at or above the threshold resets it to 0. The deploy gate blocks on a
streak of ``STREAK_LIMIT`` (7) consecutive below-threshold snapshots.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.validation_engine.models import (
    ValidationHealthSnapshot,
    ValidationRun,
    ValidationWorkflow,
    WorkflowRunStatus,
)
from app.validation_engine.synthetic_journeys import get_journey_names

logger = get_logger(__name__)

HEALTH_THRESHOLD = 90
STREAK_LIMIT = 7
JOURNEY_WINDOW = timedelta(hours=24)
HISTORY_WINDOW = timedelta(days=7)

WEIGHT_JOURNEYS = 0.60
WEIGHT_REMEDIATION = 0.20
WEIGHT_ESCALATIONS = 0.20

_ESCALATION_PENALTY = 20.0


def journey_success_percent(run_stats: Dict[str, Dict[str, int]]) -> float:
    """Aggregate completed/(completed+failed) across journeys, as a percent.

    Journeys with no runs in the window do not drag the score down.
    """
    completed = sum(int(s.get("completed", 0)) for s in run_stats.values())
    failed = sum(int(s.get("failed", 0)) for s in run_stats.values())
    total = completed + failed
    if total == 0:
        return 100.0
    return 100.0 * completed / total


def escalation_backlog_percent(open_escalations: int) -> float:
    """100 with an empty backlog, minus 20 points per open escalation."""
    return max(0.0, 100.0 - _ESCALATION_PENALTY * max(0, int(open_escalations)))


def compute_health_score(
    run_stats: Dict[str, Dict[str, int]],
    remediation_resolution_rate: Optional[float],
    open_escalations: int,
) -> int:
    """Weighted composite score. ``remediation_resolution_rate`` is 0..1 or
    None when no remediation attempts exist (treated as fully healthy)."""
    journey = journey_success_percent(run_stats)
    remediation = 100.0 if remediation_resolution_rate is None else 100.0 * remediation_resolution_rate
    backlog = escalation_backlog_percent(open_escalations)
    score = (
        WEIGHT_JOURNEYS * journey
        + WEIGHT_REMEDIATION * remediation
        + WEIGHT_ESCALATIONS * backlog
    )
    return int(round(max(0.0, min(100.0, score))))


def next_streak(previous: Optional[int], score: int) -> int:
    """Increment the below-threshold streak, or reset at/above the threshold."""
    if score < HEALTH_THRESHOLD:
        return (previous or 0) + 1
    return 0


async def compute_journey_stats(
    db: AsyncSession, window: timedelta = JOURNEY_WINDOW
) -> Dict[str, Dict[str, int]]:
    """Per-journey completed/failed counts for synthetic runs in the window."""
    cutoff = datetime.now(timezone.utc) - window
    names = get_journey_names()
    stats: Dict[str, Dict[str, int]] = {name: {"completed": 0, "failed": 0} for name in names}

    result = await db.execute(
        select(ValidationWorkflow.name, ValidationRun.status)
        .join(ValidationRun, ValidationRun.workflow_id == ValidationWorkflow.id)
        .where(
            ValidationWorkflow.name.in_(names),
            ValidationRun.created_at >= cutoff,
        )
    )
    for workflow_name, status in result.all():
        if status == WorkflowRunStatus.completed:
            stats[workflow_name]["completed"] += 1
        elif status == WorkflowRunStatus.failed:
            stats[workflow_name]["failed"] += 1
    return stats


async def compute_and_store_snapshot(db: AsyncSession) -> ValidationHealthSnapshot:
    """Collect statistics, compute the score, and append a snapshot row."""
    from app.escalations.models import EscalationEvent, EscalationStatus
    from app.remediation.engine import RemediationEngine
    from sqlalchemy import func

    run_stats = await compute_journey_stats(db)

    remediation_stats = await RemediationEngine(db).stats()
    resolution_rate: Optional[float] = (
        float(remediation_stats["resolution_rate"])
        if remediation_stats.get("total_attempts")
        else None
    )

    open_escalations = int(
        (
            await db.execute(
                select(func.count(EscalationEvent.id)).where(
                    EscalationEvent.status == EscalationStatus.open
                )
            )
        ).scalar()
        or 0
    )

    score = compute_health_score(run_stats, resolution_rate, open_escalations)

    latest_result = await db.execute(
        select(ValidationHealthSnapshot)
        .order_by(ValidationHealthSnapshot.created_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    streak = next_streak(
        latest.consecutive_below_threshold if latest else 0, score
    )

    snapshot = ValidationHealthSnapshot(
        score=score,
        run_stats=run_stats,
        consecutive_below_threshold=streak,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    logger.info(
        "validation_health_snapshot",
        score=score,
        consecutive_below_threshold=streak,
        run_stats=run_stats,
    )
    return snapshot


async def recent_snapshots(
    db: AsyncSession, window: timedelta = HISTORY_WINDOW
) -> list[ValidationHealthSnapshot]:
    """Snapshots within the history window, oldest first."""
    cutoff = datetime.now(timezone.utc) - window
    result = await db.execute(
        select(ValidationHealthSnapshot)
        .where(ValidationHealthSnapshot.created_at >= cutoff)
        .order_by(ValidationHealthSnapshot.created_at.asc())
    )
    return list(result.scalars().all())


def snapshot_to_dict(snapshot: ValidationHealthSnapshot) -> Dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "score": snapshot.score,
        "run_stats": snapshot.run_stats or {},
        "consecutive_below_threshold": snapshot.consecutive_below_threshold,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }
