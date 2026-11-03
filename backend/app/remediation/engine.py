"""Shared self-healing remediation engine.

``RemediationEngine.remediate`` looks up the enabled rule for a failure
category and runs its strategy in a bounded attempt loop (default 3 attempts
per target+rule per round). Every attempt is persisted to
``remediation_attempts`` with SHA-256 hashes of the failing state before and
after the attempt. When the attempt budget is exhausted the engine escalates:
a priority-5 ``HumanReviewQueue`` item is created and an ``escalated``
``AgentDecision`` is appended to the Merkle-chained audit trail with the full
failure chain (all attempts, including hashes) in its context package.

The engine is deliberately side-effect-light and dependency-injectable
(``sleeper``, ``attempt_fn``, ``draft_fn``) so later phases can drive it from
failure-injection tests and the learning loop without network or sleeps.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.models import HumanReviewQueue, QueueItemTypeEnum, QueueStatusEnum
from app.orchestrator.audit_chain import record_decision
from app.remediation.models import RemediationAttempt, RemediationRule
from app.remediation.rules import (
    STRATEGIES,
    AttemptFn,
    AttemptVerdict,
    DraftFn,
    RuleContext,
    Sleeper,
)

logger = get_logger(__name__)

DEFAULT_MAX_ATTEMPTS = 3
ESCALATION_PRIORITY = 5
REVIEW_FLAG_PRIORITY = 3


async def _noop_sleeper(_seconds: float) -> None:
    """Default sleeper for tests: never actually sleep."""


async def _asyncio_sleeper(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def default_sleeper() -> Sleeper:
    """Zero-delay sleeper under ENVIRONMENT=test, real asyncio.sleep otherwise."""
    if get_settings().ENVIRONMENT == "test":
        return _noop_sleeper
    return _asyncio_sleeper


def hash_state(state: dict[str, Any]) -> str:
    """SHA-256 of the canonical (sorted-key) JSON serialization of a state."""
    canonical = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class RemediationOutcome:
    """Result of a ``remediate`` round."""

    status: str  # resolved | failed | escalated
    attempts_used: int
    detail: dict[str, Any] = field(default_factory=dict)
    before_hash: str = ""
    after_hash: str | None = None
    rule_key: str | None = None


class RemediationEngine:
    """Apply remediation rules to failing targets with hashed attempt logging."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        sleeper: Sleeper | None = None,
        attempt_fn: AttemptFn | None = None,
        draft_fn: DraftFn | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ):
        self.db = db
        self.sleeper = sleeper if sleeper is not None else default_sleeper()
        self.attempt_fn = attempt_fn
        self.draft_fn = draft_fn
        self.max_attempts = max_attempts

    # ─── rule lookup ──────────────────────────────────────────────────────────

    async def _find_rule(self, category: str) -> RemediationRule | None:
        result = await self.db.execute(
            select(RemediationRule)
            .where(RemediationRule.enabled.is_(True))
            .where(
                (RemediationRule.rule_key == category)
                | (RemediationRule.category == category)
            )
            .order_by(RemediationRule.rule_key)
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ─── attempt bookkeeping ──────────────────────────────────────────────────

    async def _next_attempt_number(self, rule_key: str, target_type: str, target_id: str) -> int:
        result = await self.db.execute(
            select(func.max(RemediationAttempt.attempt_number)).where(
                RemediationAttempt.rule_key == rule_key,
                RemediationAttempt.target_type == target_type,
                RemediationAttempt.target_id == target_id,
            )
        )
        current = result.scalar() or 0
        return int(current) + 1

    async def _log_attempt(
        self,
        *,
        rule_key: str,
        target_type: str,
        target_id: str,
        project_id: uuid.UUID | None,
        attempt_number: int,
        before_hash: str,
        after_hash: str | None,
        status: str,
        detail: dict[str, Any],
        error: str | None,
        failing_state: dict[str, Any],
    ) -> RemediationAttempt:
        row = RemediationAttempt(
            rule_key=rule_key,
            target_type=target_type,
            target_id=target_id,
            project_id=project_id,
            status=status,
            attempt_number=attempt_number,
            before_state_hash=before_hash,
            after_state_hash=after_hash,
            detail={"strategy_detail": detail, "failing_state": failing_state},
            error=error,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def _failure_chain(
        self, rule_key: str, target_type: str, target_id: str
    ) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(RemediationAttempt)
            .where(
                RemediationAttempt.rule_key == rule_key,
                RemediationAttempt.target_type == target_type,
                RemediationAttempt.target_id == target_id,
            )
            .order_by(RemediationAttempt.attempt_number.asc(), RemediationAttempt.created_at.asc())
        )
        return [
            {
                "attempt_number": row.attempt_number,
                "status": row.status,
                "before_state_hash": row.before_state_hash,
                "after_state_hash": row.after_state_hash,
                "detail": row.detail,
                "error": row.error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in result.scalars().all()
        ]

    # ─── escalation ───────────────────────────────────────────────────────────

    @staticmethod
    def _target_uuid(target_id: str) -> uuid.UUID:
        try:
            return uuid.UUID(target_id)
        except (ValueError, AttributeError, TypeError):
            return uuid.uuid5(uuid.NAMESPACE_URL, f"carbonverify:remediation:{target_id}")

    async def _escalate(
        self,
        *,
        rule: RemediationRule | None,
        category: str,
        target_type: str,
        target_id: str,
        project_id: uuid.UUID | None,
        before_hash: str,
        reason: str,
    ) -> RemediationOutcome:
        rule_key = rule.rule_key if rule else category
        chain = await self._failure_chain(rule_key, target_type, target_id)

        queue_item = HumanReviewQueue(
            item_type=QueueItemTypeEnum.data_anomaly,
            item_id=self._target_uuid(target_id),
            reason=f"Remediation exhausted for '{rule_key}' on {target_type}:{target_id}. {reason}",
            priority=ESCALATION_PRIORITY,
            status=QueueStatusEnum.pending,
            sla_deadline=datetime.now(UTC) + timedelta(hours=4),
            context_json={
                "project_id": str(project_id) if project_id else None,
                "target_type": target_type,
                "target_id": target_id,
                "rule_key": rule_key,
                "failure_chain": chain,
            },
        )
        self.db.add(queue_item)
        await self.db.flush()

        decision = await record_decision(
            self.db,
            project_id=project_id,
            agent_type="remediation",
            action="escalated",
            reasoning=(
                f"Remediation rule '{rule_key}' failed after "
                f"{len(chain)} attempt(s) for {target_type}:{target_id}. {reason}"
            ),
            actor="system:remediation",
            input_summary={
                "rule_key": rule_key,
                "category": category,
                "target_type": target_type,
                "target_id": target_id,
            },
            context_package={
                "failure_chain": chain,
                "before_state_hash": before_hash,
                "queue_item_id": str(queue_item.id),
            },
            review_queue_item_id=queue_item.id,
        )
        queue_item.decision_id = decision.id
        await self.db.commit()

        logger.warning(
            "remediation_escalated",
            rule_key=rule_key,
            target_type=target_type,
            target_id=target_id,
            queue_item_id=str(queue_item.id),
        )
        return RemediationOutcome(
            status="escalated",
            attempts_used=len(chain),
            detail={
                "reason": reason,
                "queue_item_id": str(queue_item.id),
                "decision_id": str(decision.decision_id),
                "failure_chain": chain,
            },
            before_hash=before_hash,
            after_hash=chain[-1]["after_state_hash"] if chain else None,
            rule_key=rule_key,
        )

    # ─── main entry point ─────────────────────────────────────────────────────

    async def remediate(
        self,
        category: str,
        target_type: str,
        target_id: str,
        failing_state: dict[str, Any],
        project_id: uuid.UUID | None = None,
        attempts_so_far: int = 0,
    ) -> RemediationOutcome:
        """Run one remediation round for a failing target.

        ``attempts_so_far`` shrinks the attempt budget so callers that already
        spent attempts can cap the total; pass ``0`` for a fresh budget (used
        by the sweep and manual retries).
        """
        before_hash = hash_state(failing_state)
        rule = await self._find_rule(category)
        if rule is None:
            return RemediationOutcome(
                status="failed",
                attempts_used=0,
                detail={"reason": f"no enabled remediation rule for category '{category}'"},
                before_hash=before_hash,
                rule_key=None,
            )
        strategy = STRATEGIES.get(rule.strategy)
        if strategy is None:
            return RemediationOutcome(
                status="failed",
                attempts_used=0,
                detail={"reason": f"unknown strategy '{rule.strategy}'"},
                before_hash=before_hash,
                rule_key=rule.rule_key,
            )

        budget = max(1, self.max_attempts - max(0, attempts_so_far))
        attempts_used = 0
        last_detail: dict[str, Any] = {}
        last_error: str | None = None
        after_hash: str | None = None

        for _ in range(budget):
            attempt_number = await self._next_attempt_number(
                rule.rule_key, target_type, target_id
            )
            ctx = RuleContext(
                db=self.db,
                rule=rule,
                target_type=target_type,
                target_id=target_id,
                project_id=project_id,
                failing_state=failing_state,
                attempt_number=attempt_number,
                sleeper=self.sleeper,
                attempt_fn=self.attempt_fn,
                draft_fn=self.draft_fn,
            )
            try:
                verdict = await strategy(ctx)
            except Exception as exc:
                logger.exception("remediation_strategy_error", rule_key=rule.rule_key)
                verdict = AttemptVerdict(success=False, error=str(exc))

            attempts_used += 1
            new_state = verdict.state if verdict.success and verdict.state is not None else failing_state
            after_hash = hash_state(new_state)
            status = "resolved" if verdict.success else ("escalated" if verdict.deferred else "failed")
            last_detail = verdict.detail
            last_error = verdict.error

            await self._log_attempt(
                rule_key=rule.rule_key,
                target_type=target_type,
                target_id=target_id,
                project_id=project_id,
                attempt_number=attempt_number,
                before_hash=before_hash,
                after_hash=after_hash,
                status=status,
                detail=verdict.detail,
                error=verdict.error,
                failing_state=failing_state,
            )

            if verdict.success:
                return RemediationOutcome(
                    status="resolved",
                    attempts_used=attempts_used,
                    detail={
                        **verdict.detail,
                        "attempt_number": attempt_number,
                        "review_flagged": bool(verdict.detail.get("review_flagged")),
                    },
                    before_hash=before_hash,
                    after_hash=after_hash,
                    rule_key=rule.rule_key,
                )
            if verdict.deferred:
                # e.g. circuit breaker open — queue for retry, no 3-strike escalation.
                return RemediationOutcome(
                    status="escalated",
                    attempts_used=attempts_used,
                    detail={**verdict.detail, "queued_for_retry": True},
                    before_hash=before_hash,
                    after_hash=after_hash,
                    rule_key=rule.rule_key,
                )
            failing_state = new_state

        outcome = await self._escalate(
            rule=rule,
            category=category,
            target_type=target_type,
            target_id=target_id,
            project_id=project_id,
            before_hash=before_hash,
            reason=last_error or f"all {attempts_used} remediation attempts failed",
        )
        outcome.attempts_used = attempts_used
        outcome.detail = {**outcome.detail, "last_attempt_detail": last_detail}
        return outcome

    # ─── stats (API support) ──────────────────────────────────────────────────

    async def stats(self) -> dict[str, Any]:
        result = await self.db.execute(
            select(RemediationAttempt.status, func.count())
            .group_by(RemediationAttempt.status)
        )
        by_status = {row[0]: row[1] for row in result.all()}
        total = sum(by_status.values())
        resolved = by_status.get("resolved", 0)
        return {
            "total_attempts": total,
            "by_status": by_status,
            "resolved": resolved,
            "failed": by_status.get("failed", 0),
            "escalated": by_status.get("escalated", 0),
            "resolution_rate": (resolved / total) if total else 0.0,
        }
