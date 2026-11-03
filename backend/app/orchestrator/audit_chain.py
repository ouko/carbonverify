"""Merkle-chained, immutable audit trail for agent orchestration decisions.

Every agent routing decision (auto-advance, human review queueing, escalation)
and every human resolution (approve/reject/escalate, SLA auto-approve) is
appended to the ``agent_decisions`` table. Each record hashes all of its
fields plus the previous record's hash, forming a tamper-evident chain that
``verify_chain`` can validate end to end.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import AgentDecision

logger = get_logger(__name__)


def _serialize(value: Any) -> Any:
    """Best-effort JSON-safe conversion for hashing.

    Datetimes are normalized to UTC ISO strings so a record hashed before a
    commit verifies identically after a DB round-trip (SQLite returns naive
    datetimes; Postgres returns tz-aware ones).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return value


def compute_record_hash(fields: dict[str, Any]) -> str:
    """SHA-256 of the canonical (sorted-key) serialization of the field set."""
    canonical = json.dumps(
        {k: _serialize(v) for k, v in sorted(fields.items())},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_fields_for(decision: AgentDecision) -> dict[str, Any]:
    """The exact field set covered by ``record_hash``."""
    return {
        "decision_id": decision.decision_id,
        "project_id": decision.project_id,
        "agent_type": decision.agent_type,
        "action": decision.action,
        "confidence_score": decision.confidence_score,
        "reasoning": decision.reasoning,
        "input_summary": decision.input_summary,
        "context_package": decision.context_package,
        "prev_hash": decision.prev_hash,
        "actor": decision.actor,
        "review_queue_item_id": decision.review_queue_item_id,
        "created_at": decision.created_at,
    }


async def record_decision(
    db: AsyncSession,
    *,
    agent_type: str,
    action: str,
    reasoning: str,
    actor: str,
    project_id: uuid.UUID | None = None,
    decision_id: uuid.UUID | None = None,
    confidence_score: float | None = None,
    input_summary: dict[str, Any] | None = None,
    context_package: dict[str, Any] | None = None,
    review_queue_item_id: uuid.UUID | None = None,
) -> AgentDecision:
    """Append a decision to the chain and return the persisted record.

    The previous record's hash is fetched under the caller's session and the
    new record's hash covers it plus every stored field, so any later edit to
    any row (or to chain order) is detectable via :func:`verify_chain`.
    """
    # ``with_for_update`` serializes concurrent appends: a second writer
    # blocks on the chain tip until the first commits, then re-reads the new
    # tip, so two simultaneous ``record_decision`` calls cannot fork the chain
    # (both pointing at the same prev_hash), which ``verify_chain`` would
    # otherwise report as tampering. SQLite/test dialects ignore the clause.
    result = await db.execute(
        select(AgentDecision.record_hash, AgentDecision.created_at)
        .order_by(AgentDecision.created_at.desc(), AgentDecision.id.desc())
        .limit(1)
        .with_for_update()
    )
    latest = result.first()
    prev_hash = latest.record_hash if latest else None

    now = datetime.now(UTC)
    latest_created = latest.created_at if latest else None
    if latest_created and latest_created.tzinfo is None:
        latest_created = latest_created.replace(tzinfo=UTC)
    if latest_created and now <= latest_created:
        # Keep created_at strictly monotonic so chain ordering is unambiguous
        # even when many decisions are recorded within the same microsecond.
        now = latest_created + timedelta(microseconds=1)
    decision = AgentDecision(
        decision_id=decision_id or uuid.uuid4(),
        project_id=project_id,
        agent_type=agent_type,
        action=action,
        confidence_score=confidence_score,
        reasoning=reasoning,
        input_summary=input_summary,
        context_package=context_package,
        prev_hash=prev_hash,
        actor=actor,
        review_queue_item_id=review_queue_item_id,
        created_at=now,
    )
    decision.record_hash = compute_record_hash(hash_fields_for(decision))

    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    logger.info(
        "agent_decision_recorded",
        decision_id=str(decision.decision_id),
        action=action,
        agent_type=agent_type,
        actor=actor,
    )
    return decision


async def verify_chain(db: AsyncSession) -> dict[str, Any]:
    """Walk every row in chain order, recomputing hashes.

    Returns ``{"valid": bool, "checked": int, "first_broken_id": uuid|None}``
    where ``first_broken_id`` is the public ``decision_id`` of the first record
    whose recomputed hash mismatches, whose ``prev_hash`` does not match the
    preceding record's hash, or which breaks an already-broken chain.
    """
    result = await db.execute(
        select(AgentDecision).order_by(AgentDecision.created_at.asc(), AgentDecision.id.asc())
    )
    rows = result.scalars().all()

    expected_prev: str | None = None
    checked = 0
    first_broken_id: uuid.UUID | None = None
    chain_intact = True

    for row in rows:
        checked += 1
        recomputed = compute_record_hash(hash_fields_for(row))
        if (
            not chain_intact
            or recomputed != row.record_hash
            or row.prev_hash != expected_prev
        ):
            chain_intact = False
            if first_broken_id is None:
                first_broken_id = row.decision_id
        expected_prev = row.record_hash

    return {"valid": first_broken_id is None, "checked": checked, "first_broken_id": first_broken_id}
