"""AgentLearningLoop: confidence calibration from human override feedback.

Pairs agent routing decisions (``auto_advance`` / ``queued_for_review`` /
``escalated``) with subsequent human decisions (``human_approved`` /
``human_rejected`` / ``human_escalated``) on the same review queue item, plus
auto-advance decisions later reversed by a human rejection on the same
project, to compute per-agent override statistics and suggest calibrated
auto-advance thresholds.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.learning.models import LearningReport
from app.models import AgentDecision, HumanReviewQueue

logger = get_logger(__name__)

DEFAULT_AUTO_ADVANCE_THRESHOLD = 0.95
THRESHOLD_MIN = 0.85
THRESHOLD_MAX = 0.99

ROUTING_ACTIONS = ("auto_advance", "queued_for_review", "escalated")
HUMAN_ACTIONS = ("human_approved", "human_rejected", "human_escalated")
OVERRIDE_ACTIONS = ("human_rejected", "human_escalated")

# Confidence buckets for accuracy-by-confidence reporting.
BUCKET_REVIEW = "0.85-0.95"
BUCKET_AUTO = ">=0.95"


def _aware(dt: datetime | None) -> datetime | None:
    """Normalize a possibly-naive datetime (SQLite round-trip) to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _confidence_bucket(confidence: float | None) -> str | None:
    if confidence is None:
        return None
    if confidence >= 0.95:
        return BUCKET_AUTO
    if confidence >= 0.85:
        return BUCKET_REVIEW
    return None


async def _decisions_since(db: AsyncSession, days: int) -> list[AgentDecision]:
    """Load decisions from the last ``days`` days (filtered in Python because
    SQLite returns naive datetimes that do not string-compare cleanly against
    tz-aware cutoffs)."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(select(AgentDecision).order_by(AgentDecision.created_at.asc()))
    rows = result.scalars().all()
    return [r for r in rows if (_aware(r.created_at) or cutoff) >= cutoff]


def _pair_review_decisions(
    rows: list[AgentDecision],
) -> list[tuple[AgentDecision, AgentDecision]]:
    """Pair each queue item's earliest agent routing decision with its earliest
    subsequent human decision."""
    by_queue: dict[Any, dict[str, Any]] = {}
    for row in rows:
        if row.review_queue_item_id is None:
            continue
        entry = by_queue.setdefault(row.review_queue_item_id, {"agent": [], "human": []})
        if row.action in ROUTING_ACTIONS:
            entry["agent"].append(row)
        elif row.action in HUMAN_ACTIONS:
            entry["human"].append(row)

    pairs: list[tuple[AgentDecision, AgentDecision]] = []
    for entry in by_queue.values():
        if not entry["agent"] or not entry["human"]:
            continue
        agent_first = min(entry["agent"], key=lambda r: (_aware(r.created_at), r.id))
        human_after = [
            h for h in entry["human"]
            if (_aware(h.created_at) or datetime.min.replace(tzinfo=UTC))
            > (_aware(agent_first.created_at) or datetime.min.replace(tzinfo=UTC))
        ]
        if human_after:
            human_first = min(human_after, key=lambda r: (_aware(r.created_at), r.id))
            pairs.append((agent_first, human_first))
    return pairs


class LearningLoopService:
    """Computes calibration stats and weekly retraining reports from decisions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Learning feedback consumer ───────────────────────────────────────

    async def record_override(self, queue_item: HumanReviewQueue) -> dict[str, Any]:
        """Learning-feedback consumer hook for resolved review items.

        Human feedback is stored on the queue item as ``learning_feedback`` by
        the orchestrator at resolution time; this consumer is idempotent and
        backfills a normalized record for items resolved by any other path, so
        downstream calibration always has a well-shaped feedback blob.
        """
        if queue_item.learning_feedback:
            return queue_item.learning_feedback

        feedback: dict[str, Any] = {
            "human_decision": queue_item.human_decision,
            "confidence_gap": queue_item.confidence_gap,
            "agent_type": (
                queue_item.context_json.get("agent_type") if isinstance(queue_item.context_json, dict) else None
            ),
            "resolution_notes": queue_item.resolution_notes,
        }
        queue_item.learning_feedback = feedback
        await self.db.commit()
        return feedback

    # ─── Calibration ──────────────────────────────────────────────────────

    async def compute_calibration(self, days: int = 30) -> dict[str, Any]:
        """Per-agent override statistics over the trailing ``days`` window."""
        rows = await _decisions_since(self.db, days)
        pairs = _pair_review_decisions(rows)

        stats: dict[str, dict[str, Any]] = {}

        def _entry(agent_type: str) -> dict[str, Any]:
            return stats.setdefault(
                agent_type,
                {
                    "agent_type": agent_type,
                    "n_decisions": 0,
                    "n_paired_reviews": 0,
                    "n_overrides": 0,
                    "override_rate": 0.0,
                    "avg_confidence_when_overridden": None,
                    "accuracy_by_confidence_bucket": {
                        BUCKET_REVIEW: {"n": 0, "overridden": 0, "accuracy": None},
                        BUCKET_AUTO: {"n": 0, "overridden": 0, "accuracy": None},
                    },
                },
            )

        for row in rows:
            if row.action in ROUTING_ACTIONS or row.action in HUMAN_ACTIONS:
                _entry(row.agent_type)["n_decisions"] += 1

        override_confidences: dict[str, list[float]] = {}
        for agent_decision, human_decision in pairs:
            agent_type = agent_decision.agent_type
            entry = _entry(agent_type)
            entry["n_paired_reviews"] += 1
            overridden = human_decision.action in OVERRIDE_ACTIONS
            if overridden:
                entry["n_overrides"] += 1
                if agent_decision.confidence_score is not None:
                    override_confidences.setdefault(agent_type, []).append(
                        agent_decision.confidence_score
                    )
            bucket = _confidence_bucket(agent_decision.confidence_score)
            if bucket:
                bucket_entry = entry["accuracy_by_confidence_bucket"][bucket]
                bucket_entry["n"] += 1
                if overridden:
                    bucket_entry["overridden"] += 1

        for agent_type, entry in stats.items():
            if entry["n_paired_reviews"]:
                entry["override_rate"] = round(
                    entry["n_overrides"] / entry["n_paired_reviews"], 4
                )
            confs = override_confidences.get(agent_type)
            if confs:
                entry["avg_confidence_when_overridden"] = round(sum(confs) / len(confs), 4)
            for bucket_entry in entry["accuracy_by_confidence_bucket"].values():
                if bucket_entry["n"]:
                    bucket_entry["accuracy"] = round(
                        1.0 - bucket_entry["overridden"] / bucket_entry["n"], 4
                    )

        return {
            "period_days": days,
            "agents": sorted(
                stats.values(), key=lambda e: e["override_rate"], reverse=True
            ),
        }

    async def suggested_threshold(self, agent_type: str) -> float | None:
        """Lowest confidence among the agent's overridden auto-advances, clamped.

        An auto-advance is "overridden" when a later ``human_rejected`` or
        ``human_escalated`` decision exists for the same project and agent type
        (auto-advance rows carry no review-queue link, so project+agent pairing
        is used). Returns ``None`` when there is no override history.
        """
        result = await self.db.execute(
            select(AgentDecision).where(
                AgentDecision.agent_type == agent_type,
                AgentDecision.action == "auto_advance",
                AgentDecision.confidence_score.isnot(None),
            )
        )
        auto_advances = result.scalars().all()
        if not auto_advances:
            return None

        result = await self.db.execute(
            select(AgentDecision).where(
                AgentDecision.agent_type == agent_type,
                AgentDecision.action.in_(OVERRIDE_ACTIONS),
            )
        )
        rejections = result.scalars().all()
        if not rejections:
            return None

        lowest: float | None = None
        for advance in auto_advances:
            advance_at = _aware(advance.created_at) or datetime.min.replace(tzinfo=UTC)
            if advance.project_id is None:
                continue
            reversed_by_human = any(
                rejection.project_id == advance.project_id
                and (_aware(rejection.created_at) or datetime.min.replace(tzinfo=UTC))
                > advance_at
                for rejection in rejections
            )
            if reversed_by_human and advance.confidence_score is not None:
                if lowest is None or advance.confidence_score < lowest:
                    lowest = advance.confidence_score
        if lowest is None:
            return None
        return round(min(THRESHOLD_MAX, max(THRESHOLD_MIN, lowest)), 4)

    async def recent_overrides(self, limit: int = 50) -> list[dict[str, Any]]:
        """Recent human overrides paired with the agent decision they reversed."""
        result = await self.db.execute(
            select(AgentDecision)
            .where(AgentDecision.action.in_(OVERRIDE_ACTIONS))
            .order_by(AgentDecision.created_at.desc())
            .limit(limit)
        )
        human_decisions = result.scalars().all()

        paired: list[dict[str, Any]] = []
        for human in human_decisions:
            agent_pair: AgentDecision | None = None
            if human.review_queue_item_id is not None:
                pair_result = await self.db.execute(
                    select(AgentDecision)
                    .where(
                        AgentDecision.review_queue_item_id == human.review_queue_item_id,
                        AgentDecision.action.in_(ROUTING_ACTIONS),
                    )
                    .order_by(AgentDecision.created_at.asc())
                    .limit(1)
                )
                agent_pair = pair_result.scalar_one_or_none()
            paired.append({
                "queue_item_id": str(human.review_queue_item_id) if human.review_queue_item_id else None,
                "agent_type": human.agent_type,
                "human_action": human.action,
                "agent_action": agent_pair.action if agent_pair else None,
                "agent_confidence": agent_pair.confidence_score if agent_pair else None,
                "project_id": str(human.project_id) if human.project_id else None,
                "created_at": human.created_at.isoformat() if human.created_at else None,
                "reasoning": (human.reasoning or "")[:500],
            })
        return paired

    # ─── Weekly report ────────────────────────────────────────────────────

    async def weekly_retraining_report(self, persist: bool = False) -> dict[str, Any]:
        """Structured weekly brief: override-ranked agents, threshold and
        retraining suggestions, top override reasons, and a markdown brief."""
        calibration = await self.compute_calibration(days=7)

        suggested_adjustments: list[str] = []
        ranked_agents: list[dict[str, Any]] = []
        for entry in calibration["agents"]:
            agent_type = entry["agent_type"]
            threshold = await self.suggested_threshold(agent_type)
            ranked = {**entry, "suggested_threshold": threshold}
            ranked_agents.append(ranked)
            if threshold is not None and threshold > DEFAULT_AUTO_ADVANCE_THRESHOLD:
                suggested_adjustments.append(
                    f"{agent_type}: raise auto-advance threshold to {threshold:.2f} "
                    f"(override rate {entry['override_rate']:.1%} across "
                    f"{entry['n_paired_reviews']} reviewed decision(s))"
                )
            elif entry["n_paired_reviews"] >= 5 and entry["override_rate"] > 0.2:
                suggested_adjustments.append(
                    f"{agent_type}: high override rate ({entry['override_rate']:.1%}) "
                    "with no auto-advance reversals — consider additional training data "
                    "or a manual threshold review."
                )

        reason_counts = await self._top_override_reasons(limit=5)

        report: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "period_days": 7,
            "agents": ranked_agents,
            "suggested_adjustments": suggested_adjustments,
            "top_override_reasons": reason_counts,
            "markdown": self._format_markdown(ranked_agents, suggested_adjustments, reason_counts),
        }

        if persist:
            self.db.add(LearningReport(report_type="weekly_retraining", report=report))
            await self.db.commit()
        return report

    async def _top_override_reasons(self, limit: int = 5) -> list[dict[str, Any]]:
        """Most common override justifications from review-queue learning feedback."""
        result = await self.db.execute(select(HumanReviewQueue))
        items = result.scalars().all()
        counts: dict[str, int] = {}
        for item in items:
            feedback = item.learning_feedback or {}
            if feedback.get("human_decision") not in OVERRIDE_ACTIONS:
                continue
            reason = (feedback.get("resolution_notes") or "").strip()
            if reason:
                counts[reason] = counts.get(reason, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [{"reason": reason, "count": count} for reason, count in ranked]

    @staticmethod
    def _format_markdown(
        agents: list[dict[str, Any]],
        adjustments: list[str],
        reasons: list[dict[str, Any]],
    ) -> str:
        lines = ["# Weekly Agent Retraining Brief", ""]
        lines.append("## Override ranking")
        if not agents:
            lines.append("_No agent decisions in the reporting window._")
        for entry in agents:
            threshold = entry.get("suggested_threshold")
            threshold_txt = f"{threshold:.2f}" if threshold is not None else "n/a"
            lines.append(
                f"- **{entry['agent_type']}**: override rate "
                f"{entry['override_rate']:.1%} ({entry['n_overrides']}/"
                f"{entry['n_paired_reviews']} reviewed), "
                f"suggested threshold {threshold_txt}"
            )
        lines.append("")
        lines.append("## Suggested adjustments")
        if adjustments:
            lines.extend(f"- {a}" for a in adjustments)
        else:
            lines.append("_No threshold adjustments suggested this week._")
        lines.append("")
        lines.append("## Top override reasons")
        if reasons:
            lines.extend(f"- {r['reason']} (x{r['count']})" for r in reasons)
        else:
            lines.append("_No override reasons recorded._")
        return "\n".join(lines)


async def get_effective_threshold(db: AsyncSession, agent_type: str) -> float:
    """Auto-advance threshold for an agent: learned suggestion, else 0.95.

    Defensive by contract — any failure falls back to the platform default so
    orchestration is never blocked by the learning loop.
    """
    try:
        threshold = await LearningLoopService(db).suggested_threshold(agent_type)
    except Exception as exc:  # noqa: BLE001 — calibration must never break dispatch
        logger.warning("effective_threshold_lookup_failed", agent_type=agent_type, error=str(exc))
        return DEFAULT_AUTO_ADVANCE_THRESHOLD
    if threshold is None:
        return DEFAULT_AUTO_ADVANCE_THRESHOLD
    return threshold
