"""Hermetic tests for the shared self-healing remediation engine.

No real sleeping (injectable sleeper spies), no network (Kimi falls back to a
deterministic local response when no API key is configured).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, update

from app.models import AgentDecision, HumanReviewQueue, QueueItemTypeEnum
from app.remediation.engine import RemediationEngine, hash_state
from app.remediation.models import RemediationAttempt, RemediationRule
from app.remediation.rules import DEFAULT_RULES, seed_default_rules

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def seeded_rules(db_session):
    rules = await seed_default_rules(db_session)
    assert len(rules) == len(DEFAULT_RULES)
    return rules


@pytest.fixture
def sleeper_spy():
    calls = []

    async def spy(seconds: float) -> None:
        calls.append(seconds)

    return spy, calls


async def _attempts(db_session, rule_key=None, target_id=None):
    stmt = select(RemediationAttempt)
    if rule_key:
        stmt = stmt.where(RemediationAttempt.rule_key == rule_key)
    if target_id:
        stmt = stmt.where(RemediationAttempt.target_id == target_id)
    stmt = stmt.order_by(RemediationAttempt.attempt_number)
    result = await db_session.execute(stmt)
    return result.scalars().all()


# ─── seeding ──────────────────────────────────────────────────────────────────


async def test_seed_default_rules_idempotent(db_session):
    first = await seed_default_rules(db_session)
    second = await seed_default_rules(db_session)

    result = await db_session.execute(select(RemediationRule))
    rows = result.scalars().all()
    assert len(rows) == len(DEFAULT_RULES)
    assert {r.id for r in first} == {r.id for r in second}
    assert {r.rule_key for r in rows} == {r["rule_key"] for r in DEFAULT_RULES}


# ─── a. auto_correct ──────────────────────────────────────────────────────────


async def test_auto_correct_resolves(db_session, seeded_rules, sleeper_spy):
    sleeper, calls = sleeper_spy
    engine = RemediationEngine(db_session, sleeper=sleeper)
    failing_state = {
        "form": {"fuel_type": None, "region": "Nairobi"},
        "errors": {"fuel_type": "required"},
        "defaults": {"fuel_type": "wood"},
    }
    before = hash_state(failing_state)

    outcome = await engine.remediate(
        "form_validation_error", "upload", "form-1", failing_state
    )

    assert outcome.status == "resolved"
    assert outcome.attempts_used == 1
    assert outcome.before_hash == before
    assert outcome.after_hash != before
    assert outcome.after_hash is not None
    assert outcome.detail["corrections"]["fuel_type"] == {"from": None, "to": "wood"}

    rows = await _attempts(db_session, target_id="form-1")
    assert len(rows) == 1
    assert rows[0].status == "resolved"
    assert rows[0].before_state_hash == before
    assert rows[0].after_state_hash == outcome.after_hash
    assert calls == []  # auto_correct never sleeps


# ─── b. backoff_retry ─────────────────────────────────────────────────────────


async def test_backoff_retry_resolves_second_attempt(db_session, seeded_rules, sleeper_spy):
    sleeper, calls = sleeper_spy
    engine = RemediationEngine(db_session, sleeper=sleeper)
    failing_state = {
        "service": "radix_gateway",  # circuit closed by default
        "errors": ["rate limit exceeded"],
        "retry_outcome": [False, True],
    }

    outcome = await engine.remediate(
        "api_timeout_rate_limit", "api_call", "call-1", failing_state
    )

    assert outcome.status == "resolved"
    assert outcome.attempts_used == 2
    # Backoff schedule: 1s, 2s (base 1, factor 2) — recorded, never really slept.
    assert len(calls) == 2
    assert calls[0] >= 1.0
    assert calls[1] >= 2.0

    rows = await _attempts(db_session, target_id="call-1")
    assert [r.status for r in rows] == ["failed", "resolved"]
    assert rows[0].detail["strategy_detail"]["delay_seconds"] == 1.0
    assert rows[1].detail["strategy_detail"]["delay_seconds"] == 2.0


async def test_backoff_retry_open_circuit_defers(db_session, seeded_rules, sleeper_spy, monkeypatch):
    from app.core.circuit_breaker import CIRCUIT_BREAKERS, CircuitState

    breaker = CIRCUIT_BREAKERS["kimi_api"]
    monkeypatch.setattr(breaker, "state", CircuitState.OPEN)
    sleeper, calls = sleeper_spy
    engine = RemediationEngine(db_session, sleeper=sleeper)

    outcome = await engine.remediate(
        "api_timeout_rate_limit",
        "api_call",
        "call-cb",
        {"service": "kimi_api", "errors": ["timeout"], "retry_outcome": True},
    )

    assert outcome.status == "escalated"
    assert outcome.detail["queued_for_retry"] is True
    assert outcome.detail["reason"] == "circuit_breaker_open"
    assert calls == []  # never slept — short-circuited

    rows = await _attempts(db_session, target_id="call-cb")
    assert len(rows) == 1
    assert rows[0].status == "escalated"


async def test_backoff_retry_no_signal_queues_for_retry(db_session, seeded_rules, sleeper_spy):
    sleeper, calls = sleeper_spy
    engine = RemediationEngine(db_session, sleeper=sleeper)

    outcome = await engine.remediate(
        "api_timeout_rate_limit",
        "api_call",
        "call-nosig",
        {"service": "radix_gateway", "errors": ["timeout"]},
    )

    # Without a success signal the engine defers instead of burning strikes.
    assert outcome.status == "escalated"
    assert outcome.detail["queued_for_retry"] is True
    assert len(calls) == 1


async def test_backoff_retry_attempt_fn_injection(db_session, seeded_rules, sleeper_spy):
    sleeper, _calls = sleeper_spy
    attempts = []

    async def flaky_executor(ctx):
        attempts.append(ctx.attempt_number)
        return len(attempts) >= 2

    engine = RemediationEngine(db_session, sleeper=sleeper, attempt_fn=flaky_executor)
    outcome = await engine.remediate(
        "api_timeout_rate_limit",
        "api_call",
        "call-fn",
        {"service": "radix_gateway", "errors": ["timeout"]},
    )

    assert outcome.status == "resolved"
    assert attempts == [1, 2]


# ─── c. jitter_retry ──────────────────────────────────────────────────────────


async def test_jitter_retry_resolves(db_session, seeded_rules, sleeper_spy):
    sleeper, calls = sleeper_spy
    engine = RemediationEngine(db_session, sleeper=sleeper)

    outcome = await engine.remediate(
        "db_deadlock",
        "calculation",
        "calc-1",
        {"operation": "UPDATE calculations", "retry_outcome": True},
    )

    assert outcome.status == "resolved"
    assert len(calls) == 1
    assert 0.0 <= calls[0] <= 0.5 + 1e-9
    rows = await _attempts(db_session, target_id="calc-1")
    assert rows[0].status == "resolved"


# ─── d. conservative_fallback ─────────────────────────────────────────────────


async def test_conservative_fallback_flags_review(db_session, seeded_rules):
    engine = RemediationEngine(db_session)
    failing_state = {
        "anomaly_report": {
            "field": "emissions_reduction_tco2e",
            "value": 12500.0,
            "lower_bound": 9800.0,
        }
    }

    outcome = await engine.remediate(
        "calculation_anomaly", "calculation", "calc-anom", failing_state, project_id=None
    )

    assert outcome.status == "resolved"
    assert outcome.detail["review_flagged"] is True
    assert outcome.after_hash != outcome.before_hash

    result = await db_session.execute(select(HumanReviewQueue))
    items = result.scalars().all()
    assert len(items) == 1
    assert items[0].priority == 3
    assert items[0].item_type == QueueItemTypeEnum.calculation
    assert "Conservative fallback applied" in items[0].reason

    # A second remediation for another target must not double-flag the same one.
    assert outcome.detail["review_item_id"] == str(items[0].id)


async def test_conservative_fallback_without_lower_bound_fails(db_session, seeded_rules):
    engine = RemediationEngine(db_session)
    outcome = await engine.remediate(
        "calculation_anomaly",
        "calculation",
        "calc-nolb",
        {"anomaly_report": {"field": "x", "value": 10}},
    )
    assert outcome.status == "escalated"  # 3 failed attempts → escalation
    rows = await _attempts(db_session, target_id="calc-nolb")
    assert len(rows) == 3
    assert all(r.status == "failed" for r in rows)


# ─── e. interpolate_or_exclude ────────────────────────────────────────────────


async def test_interpolation_of_small_stable_gap(db_session, seeded_rules):
    engine = RemediationEngine(db_session)
    failing_state = {"series": [10.0, 12.0, None, None, 14.0, 13.0, 15.0]}

    outcome = await engine.remediate(
        "missing_data_gap", "data_gap", "gap-1", failing_state
    )

    assert outcome.status == "resolved"
    assert outcome.detail["decision"] == "interpolated"
    assert outcome.detail["interpolated_indices"] == [2, 3]

    rows = await _attempts(db_session, target_id="gap-1")
    assert len(rows) == 1
    assert rows[0].after_state_hash != rows[0].before_state_hash
    # Linear interpolation: idx2 = 12 + (14-12)/3, idx3 = 12 + 2*(14-12)/3.
    expected = hash_state(
        {
            "series": [10.0, 12.0, 12 + 2 / 3, 12 + 4 / 3, 14.0, 13.0, 15.0],
            "provenance": {
                "method": "linear_interpolation",
                "source": "remediation",
                "interpolated_indices": [2, 3],
            },
        }
    )
    assert rows[0].after_state_hash == expected
    # Original failing state is preserved as an immutable snapshot.
    assert rows[0].detail["failing_state"] is not None


async def test_exclusion_when_gap_too_large(db_session, seeded_rules):
    engine = RemediationEngine(db_session)
    failing_state = {"series": [10.0, None, None, None, 14.0, 13.0, 15.0, 12.0]}

    outcome = await engine.remediate(
        "missing_data_gap", "data_gap", "gap-2", failing_state
    )

    assert outcome.status == "resolved"
    assert outcome.detail["decision"] == "excluded"
    justification = outcome.detail["justification"]
    assert "exceeds" in justification

    rows = await _attempts(db_session, target_id="gap-2")
    strategy_detail = rows[0].detail["strategy_detail"]
    assert strategy_detail["excluded_indices"] == [1, 2, 3]
    assert "excluded" in str(rows[0].detail)


async def test_exclusion_when_too_few_observed(db_session, seeded_rules):
    engine = RemediationEngine(db_session)
    outcome = await engine.remediate(
        "missing_data_gap", "data_gap", "gap-3", {"series": [10.0, None, None]}
    )
    assert outcome.status == "resolved"
    assert outcome.detail["decision"] == "excluded"
    assert "statistically unsupported" in outcome.detail["justification"]


async def test_exclusion_when_variance_unstable(db_session, seeded_rules):
    engine = RemediationEngine(db_session)
    # Observed values swing wildly → CV > 0.5.
    failing_state = {"series": [1.0, 100.0, None, None, 4.0, 250.0, 8.0]}
    outcome = await engine.remediate(
        "missing_data_gap", "data_gap", "gap-4", failing_state
    )
    assert outcome.status == "resolved"
    assert outcome.detail["decision"] == "excluded"
    assert "variance unstable" in outcome.detail["justification"]


# ─── f. kb_draft_response ─────────────────────────────────────────────────────


async def test_kb_draft_response_via_injected_drafter(db_session, seeded_rules):
    async def drafter(ctx):
        return "Draft: fNRB is the fraction of non-renewable biomass."

    engine = RemediationEngine(db_session, draft_fn=drafter)
    outcome = await engine.remediate(
        "vvb_clarification",
        "vvb_clarification",
        "vvb-1",
        {"query_text": "Explain fNRB", "project_data": {"name": "Demo"}},
    )

    assert outcome.status == "resolved"
    assert outcome.detail["kb_source"] == "injected_draft_fn"
    rows = await _attempts(db_session, target_id="vvb-1")
    assert rows[0].status == "resolved"


async def test_kb_draft_response_kimi_fallback(db_session, seeded_rules):
    """No API key configured → Kimi client returns its deterministic local
    fallback content, so the draft still resolves with zero network."""
    engine = RemediationEngine(db_session)
    outcome = await engine.remediate(
        "vvb_clarification",
        "vvb_clarification",
        "vvb-2",
        {"query_text": "Clarify leakage treatment", "project_data": {"name": "Demo"}},
    )

    assert outcome.status == "resolved"
    assert outcome.detail["kb_source"] == "kimi_api"
    assert outcome.detail["draft_length"] > 0


async def test_kb_draft_response_empty_query_fails(db_session, seeded_rules):
    engine = RemediationEngine(db_session)
    outcome = await engine.remediate(
        "vvb_clarification", "vvb_clarification", "vvb-3", {"query_text": "  "}
    )
    assert outcome.status == "escalated"


# ─── 3-strike escalation ──────────────────────────────────────────────────────


async def test_three_strikes_escalates_with_audit_trail(db_session, seeded_rules):
    engine = RemediationEngine(db_session)
    failing_state = {
        "form": {"fuel_type": None},
        "errors": {"fuel_type": "required"},
        "defaults": {},  # nothing to correct with → every attempt fails
    }

    outcome = await engine.remediate(
        "form_validation_error",
        "upload",
        "form-strike",
        failing_state,
        project_id=None,
    )

    assert outcome.status == "escalated"
    assert outcome.attempts_used == 3

    rows = await _attempts(db_session, target_id="form-strike")
    assert len(rows) == 3
    assert [r.attempt_number for r in rows] == [1, 2, 3]
    assert all(r.status == "failed" for r in rows)
    assert all(r.before_state_hash == rows[0].before_state_hash for r in rows)

    # Priority-5 human review escalation item.
    result = await db_session.execute(select(HumanReviewQueue))
    items = result.scalars().all()
    assert len(items) == 1
    assert items[0].priority == 5
    assert items[0].status.value == "pending"
    assert "form_validation_error" in items[0].reason

    # Escalated AgentDecision with the full failure chain in context_package.
    result = await db_session.execute(select(AgentDecision))
    decisions = result.scalars().all()
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.action == "escalated"
    assert decision.actor == "system:remediation"
    assert decision.agent_type == "remediation"
    chain = decision.context_package["failure_chain"]
    assert len(chain) == 3
    assert {c["status"] for c in chain} == {"failed"}
    assert all(c["before_state_hash"] for c in chain)
    assert decision.context_package["queue_item_id"] == str(items[0].id)
    assert items[0].decision_id == decision.id


async def test_unknown_category_returns_failed_without_attempts(db_session, seeded_rules):
    engine = RemediationEngine(db_session)
    outcome = await engine.remediate(
        "does_not_exist", "upload", "x-1", {"whatever": True}
    )
    assert outcome.status == "failed"
    assert outcome.attempts_used == 0
    assert "no enabled remediation rule" in outcome.detail["reason"]
    rows = await _attempts(db_session, target_id="x-1")
    assert rows == []


# ─── sweep task ───────────────────────────────────────────────────────────────


async def test_remediation_sweep_reruns_old_failures(
    db_session, seeded_rules, patch_db_context
):
    from app.tasks.lifecycle_jobs import remediation_sweep

    # A stale failed attempt (2h old) whose stored failing_state will now succeed.
    stale = RemediationAttempt(
        rule_key="api_timeout_rate_limit",
        target_type="api_call",
        target_id="stale-1",
        status="failed",
        attempt_number=1,
        before_state_hash=hash_state({"errors": ["timeout"]}),
        after_state_hash=None,
        detail={
            "strategy_detail": {"attempt_signal": False},
            "failing_state": {"service": "radix_gateway", "retry_outcome": True},
        },
        error="retry did not resolve the failure",
    )
    db_session.add(stale)
    await db_session.commit()

    old = datetime.now(UTC) - timedelta(hours=2)
    await db_session.execute(
        update(RemediationAttempt)
        .where(RemediationAttempt.id == stale.id)
        .values(created_at=old)
    )
    await db_session.commit()

    result = remediation_sweep()

    assert result["stale_targets"] == 1
    assert result["rerun"] == 1

    rows = await _attempts(db_session, target_id="stale-1")
    # Original failure + the fresh resolved attempt (number continues).
    assert [(r.attempt_number, r.status) for r in rows] == [(1, "failed"), (2, "resolved")]


async def test_remediation_sweep_ignores_recent_failures(
    db_session, seeded_rules, patch_db_context
):
    from app.tasks.lifecycle_jobs import remediation_sweep

    fresh = RemediationAttempt(
        rule_key="api_timeout_rate_limit",
        target_type="api_call",
        target_id="fresh-1",
        status="failed",
        attempt_number=3,
        before_state_hash=hash_state({"errors": ["timeout"]}),
        detail={"failing_state": {"retry_outcome": True}},
        error="retry did not resolve the failure",
    )
    db_session.add(fresh)
    await db_session.commit()

    result = remediation_sweep()
    assert result["stale_targets"] == 0
    assert result["rerun"] == 0


# ─── API ──────────────────────────────────────────────────────────────────────


async def test_api_requires_auth(client, seeded_rules):
    resp = await client.get("/api/v1/remediation/rules")
    assert resp.status_code == 401
    resp = await client.get("/api/v1/remediation/attempts")
    assert resp.status_code == 401
    resp = await client.get("/api/v1/remediation/stats")
    assert resp.status_code == 401


async def test_api_rules_and_stats(authenticated_client, db_session, seeded_rules):
    ac, _user = authenticated_client

    resp = await ac.get("/api/v1/remediation/rules")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rules"]) == len(DEFAULT_RULES)
    rule_keys = {r["rule_key"] for r in body["rules"]}
    assert "form_validation_error" in rule_keys
    assert "vvb_clarification" in rule_keys

    resp = await ac.get("/api/v1/remediation/rules", params={"enabled": "false"})
    assert resp.json()["rules"] == []

    resp = await ac.get("/api/v1/remediation/stats")
    assert resp.status_code == 200
    assert resp.json()["total_attempts"] == 0
    assert resp.json()["resolution_rate"] == 0.0


async def test_api_attempts_filters_and_retry(authenticated_client, db_session, seeded_rules):
    ac, _user = authenticated_client
    engine = RemediationEngine(db_session)

    await engine.remediate(
        "db_deadlock",
        "calculation",
        "api-calc",
        {"retry_outcome": True},
    )
    failing = {
        "form": {"fuel_type": None},
        "errors": {"fuel_type": "required"},
        "defaults": {},
    }
    await engine.remediate("form_validation_error", "upload", "api-form", failing)

    # Filter by status.
    resp = await ac.get("/api/v1/remediation/attempts", params={"status": "resolved"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["attempts"][0]["target_id"] == "api-calc"

    # Filter by rule_key + target_type.
    resp = await ac.get(
        "/api/v1/remediation/attempts",
        params={"rule_key": "form_validation_error", "target_type": "upload"},
    )
    assert resp.json()["total"] == 3  # three failed strikes

    # Pagination shape.
    resp = await ac.get("/api/v1/remediation/attempts", params={"limit": 2, "offset": 0})
    body = resp.json()
    assert body["limit"] == 2
    assert len(body["attempts"]) == 2
    assert body["total"] == 4

    # Manual retry (operator role — authenticated user is admin): seed a
    # default so the re-run resolves.
    resp = await ac.get(
        "/api/v1/remediation/attempts",
        params={"rule_key": "form_validation_error"},
    )
    attempt_id = resp.json()["attempts"][0]["id"]

    rule_result = await db_session.execute(
        select(RemediationRule).where(RemediationRule.rule_key == "form_validation_error")
    )
    rule = rule_result.scalar_one()
    rule.config = {"defaults": {"fuel_type": "wood"}}
    await db_session.commit()

    resp = await ac.post(f"/api/v1/remediation/attempts/{attempt_id}/retry")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"

    # Unknown attempt id → 404.
    resp = await ac.post(f"/api/v1/remediation/attempts/{uuid.uuid4()}/retry")
    assert resp.status_code == 404
