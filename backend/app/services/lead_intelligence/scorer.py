"""Stuck-ness scoring algorithm for carbon registry leads."""

from datetime import date, timedelta
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Methodology complexity weights (0-15)
METHODOLOGY_WEIGHTS = {
    "VM0050": 15.0,
    "AMS-II.G": 12.0,
    "AMS-II.G.": 12.0,
    "VMR0006": 10.0,
    "TPDDTEC_v4": 8.0,
    "TPDDTEC v4": 8.0,
    "VM0055": 14.0,
    "AMS-I.E": 11.0,
    "AMS-I.E.": 11.0,
}

# Registry-specific stuck thresholds (days)
STUCK_THRESHOLDS = {
    "under_verification": 180,
    "under_validation": 365,
    "registered": 730,
    "under_certification": 270,
    "certified_design": 365,
}


def _time_in_stage_score(days_in_status: Optional[int], status: str) -> float:
    """Score 0-40 based on how long a project has been in its current stage."""
    if days_in_status is None or days_in_status <= 0:
        return 0.0

    threshold = STUCK_THRESHOLDS.get(status.lower().replace(" ", "_"), 365)
    ratio = min(days_in_status / threshold, 2.0)
    return min(40.0 * (ratio / 1.0 if ratio >= 1.0 else ratio * 0.5), 40.0)


def _deadline_proximity_score(crediting_period_end: Optional[date]) -> float:
    """Score 0-25 based on how close the crediting period end is."""
    if crediting_period_end is None:
        return 0.0

    today = date.today()
    days_until = (crediting_period_end - today).days

    if days_until < 0:
        return 25.0  # Already expired
    if days_until > 180:
        return 0.0

    return 25.0 * (1.0 - (days_until / 180.0))


def _verification_gap_score(last_verification_date: Optional[date]) -> float:
    """Score 0-20 based on how long since last verification."""
    if last_verification_date is None:
        return 10.0  # Unknown = moderate risk

    days_since = (date.today() - last_verification_date).days
    if days_since <= 365:
        return 0.0
    if days_since >= 730:
        return 20.0

    return 20.0 * ((days_since - 365) / 365.0)


def _methodology_complexity_score(methodology: Optional[str]) -> float:
    """Score 0-15 based on methodology complexity."""
    if not methodology:
        return 7.5

    key = methodology.strip()
    return METHODOLOGY_WEIGHTS.get(key, 7.5)


def score_lead(
    days_in_status: Optional[int],
    status: str,
    crediting_period_end: Optional[date],
    last_verification_date: Optional[date],
    methodology: Optional[str],
) -> float:
    """Compute composite stuck score (0-100).

    Returns:
        Float between 0.0 and 100.0.
    """
    time_score = _time_in_stage_score(days_in_status, status)
    deadline_score = _deadline_proximity_score(crediting_period_end)
    verification_score = _verification_gap_score(last_verification_date)
    methodology_score = _methodology_complexity_score(methodology)

    total = time_score + deadline_score + verification_score + methodology_score
    return round(min(total, 100.0), 2)


def priority_from_score(score: float) -> str:
    """Map stuck score to priority label."""
    if score >= 76:
        return "critical"
    if score >= 56:
        return "high"
    if score >= 31:
        return "medium"
    return "low"
