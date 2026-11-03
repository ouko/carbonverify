"""Composite health-score computation and snapshot storage for continuous validation.

Pure scoring functions (``compute_*``) are importable and unit-testable without
a database; ``compute_and_store_snapshot`` collects the underlying statistics
and appends a ``validation_health_snapshots`` row.

Score formula (0-100, higher is healthier):

- Synthetic journey success rate (last 24h) — weight 60%
- Remediation resolution rate (shared remediation engine attempts) — weight 20%
- Escalation backlog (open escalation events) — weight 20%

Snapshots are still recorded every 15 minutes, but the deploy gate semantics
are DAILY: each UTC calendar day is scored by its WORST (minimum) snapshot.
``consecutive_below_threshold`` counts consecutive UTC days (ending today)
whose daily score is below ``HEALTH_THRESHOLD`` (90); a day at or above the
threshold resets it to 0. The deploy gate blocks on a streak of
``STREAK_LIMIT`` (7) consecutive below-threshold days.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

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


def journey_success_percent(run_stats: dict[str, dict[str, int]]) -> float:
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
    run_stats: dict[str, dict[str, int]],
    remediation_resolution_rate: float | None,
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
    return round(max(0.0, min(100.0, score)))


def utc_day(created_at: datetime) -> date:
    """UTC calendar day for a snapshot timestamp (naive values are assumed UTC)."""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at.astimezone(UTC).date()


def streak_from_daily_scores(scores: dict[date, int]) -> int:
    """Consecutive below-threshold days ending today (UTC).

    Today counts once its daily score is present; a missing today means the
    streak resets (there is no evidence today is below the threshold yet).
    """
    today = datetime.now(UTC).date()
    day_score = scores.get(today)
    if day_score is None or day_score >= HEALTH_THRESHOLD:
        return 0
    streak = 0
    day = today
    while scores.get(day) is not None and scores[day] < HEALTH_THRESHOLD:
        streak += 1
        day -= timedelta(days=1)
    return streak


async def daily_scores(db: AsyncSession, days: int = 8) -> dict[date, int]:
    """Worst (minimum) snapshot score per UTC calendar day for the last ``days``
    days. The minimum is used so one bad 15-minute window marks the whole day
    below threshold (conservative, per the deploy-gate product spec)."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(
        select(ValidationHealthSnapshot).where(ValidationHealthSnapshot.created_at >= cutoff)
    )
    scores: dict[date, int] = {}
    for snapshot in result.scalars().all():
        day = utc_day(snapshot.created_at)
        if day not in scores or snapshot.score < scores[day]:
            scores[day] = snapshot.score
    return scores


async def compute_journey_stats(
    db: AsyncSession, window: timedelta = JOURNEY_WINDOW
) -> dict[str, dict[str, int]]:
    """Per-journey completed/failed counts for synthetic runs in the window."""
    cutoff = datetime.now(UTC) - window
    names = get_journey_names()
    stats: dict[str, dict[str, int]] = {name: {"completed": 0, "failed": 0} for name in names}

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
    from sqlalchemy import func

    from app.escalations.models import EscalationEvent, EscalationStatus
    from app.remediation.engine import RemediationEngine

    run_stats = await compute_journey_stats(db)

    remediation_stats = await RemediationEngine(db).stats()
    resolution_rate: float | None = (
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

    # Daily streak: completed days plus today's snapshots so far, with the
    # score being stored folded into today's daily (worst-of-day) score.
    day_scores = await daily_scores(db, days=STREAK_LIMIT + 1)
    today = datetime.now(UTC).date()
    day_scores[today] = min(day_scores.get(today, score), score)
    streak = streak_from_daily_scores(day_scores)

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
    cutoff = datetime.now(UTC) - window
    result = await db.execute(
        select(ValidationHealthSnapshot)
        .where(ValidationHealthSnapshot.created_at >= cutoff)
        .order_by(ValidationHealthSnapshot.created_at.asc())
    )
    return list(result.scalars().all())


def snapshot_to_dict(snapshot: ValidationHealthSnapshot) -> dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "score": snapshot.score,
        "run_stats": snapshot.run_stats or {},
        "consecutive_below_threshold": snapshot.consecutive_below_threshold,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }
