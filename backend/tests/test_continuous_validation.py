"""Continuous validation: synthetic journeys, health snapshots, deploy gate.

Hermetic: SQLite in-memory, no network (Radix anchoring is simulated because
RADIX_ENABLED defaults to False), no real sleeping (ENVIRONMENT=test gives the
remediation engine a no-op sleeper).
"""

import importlib
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.escalations.models import EscalationEvent, EscalationStatus
from app.remediation.models import RemediationAttempt
from app.tasks.validation_jobs import has_inflight_run, run_synthetic_journeys
from app.validation_engine.health import (
    compute_and_store_snapshot,
    compute_health_score,
    compute_journey_stats,
    daily_scores,
    escalation_backlog_percent,
    journey_success_percent,
    streak_from_daily_scores,
    utc_day,
)
from app.validation_engine.journey_service import (
    ensure_journey_service_registered,
    journey_service,
)
from app.validation_engine.models import (
    HumanEscalation,
    ValidationHealthSnapshot,
    ValidationProof,
    ValidationRun,
    WorkflowRunStatus,
)
from app.validation_engine.orchestrator import ValidationOrchestrator
from app.validation_engine.schemas import WorkflowGraph
from app.validation_engine.synthetic_journeys import (
    ensure_journey_workflows,
    get_journey_names,
    get_journey_templates,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def session_local_patch(engine, monkeypatch):
    """Route app.database.AsyncSessionLocal to the test engine so
    DatabaseQueryExecutor steps query the same in-memory SQLite database."""
    import app.database as app_database

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(app_database, "AsyncSessionLocal", session_factory)
    return session_factory


@pytest_asyncio.fixture
async def journey_setup(db_session, patch_db_context, session_local_patch):
    ensure_journey_service_registered()
    templates = get_journey_templates()
    workflows = await ensure_journey_workflows(db_session, templates)
    return templates, workflows


def _journey_input() -> dict:
    suffix = uuid.uuid4().hex[:8]
    return {
        "journey": "",
        "synthetic": True,
        "actor_marker": f"TEST-{suffix}",
        "project_name": f"synth-test-{suffix}",
        "target_name": suffix,
    }


async def _execute_journey(db_session, workflows, name: str) -> ValidationRun:
    workflow = workflows[name]
    input_data = _journey_input()
    input_data["journey"] = name
    orchestrator = ValidationOrchestrator(db_session)
    run = await orchestrator.create_run(
        workflow_id=str(workflow.id),
        trigger_event="synthetic_test",
        input_data=input_data,
    )
    await orchestrator.execute_workflow(str(run.id))
    result = await db_session.execute(select(ValidationRun).where(ValidationRun.id == run.id))
    return result.scalar_one()


async def _seed_journey_run(
    db_session, workflows, name: str, status: WorkflowRunStatus
) -> ValidationRun:
    run = ValidationRun(
        workflow_id=workflows[name].id,
        trigger_event="synthetic_test",
        status=status,
        input_data={"journey": name, "synthetic": True},
    )
    db_session.add(run)
    await db_session.commit()
    return run


# ─── Template validation ──────────────────────────────────────────────────────

class TestJourneyTemplates:
    def test_all_three_templates_present(self):
        templates = get_journey_templates()
        assert sorted(templates) == sorted([
            "synthetic_developer_journey",
            "synthetic_enumerator_journey",
            "synthetic_calc_anomaly_recovery",
        ])

    @pytest.mark.parametrize("name", get_journey_names())
    def test_template_validates_against_workflow_graph(self, name):
        templates = get_journey_templates()
        graph = WorkflowGraph.model_validate(templates[name])
        assert graph.entry_step
        assert len(graph.steps) >= 3

    def test_templates_are_distinct(self):
        templates = get_journey_templates()
        assert len({id(g) for g in templates.values()}) == 3


# ─── End-to-end journey execution ─────────────────────────────────────────────

class TestJourneyExecution:
    @pytest.mark.asyncio
    async def test_developer_journey_completes_with_proofs(self, db_session, journey_setup):
        _, workflows = journey_setup
        run = await _execute_journey(db_session, workflows, "synthetic_developer_journey")

        assert run.status == WorkflowRunStatus.completed
        assert run.merkle_root and len(run.merkle_root) == 64
        proofs = (
            await db_session.execute(select(ValidationProof).where(ValidationProof.run_id == run.id))
        ).scalars().all()
        assert len(proofs) >= 4
        # Step output recorded the full lifecycle walk.
        assert run.output_data["run_calculation"]["result"]["project_status"] == "review"
        assert run.output_data["run_calculation"]["result"]["transition_log"] == [
            "onboarding", "data_collection", "calculation", "review",
        ]
        # The project actually reached review in the database.
        from app.models import Project, ProjectStatusEnum, Report

        project_result = await db_session.execute(select(Project).where(Project.name == run.input_data["project_name"]))
        project = project_result.scalar_one()
        assert project.status == ProjectStatusEnum.review
        report_count = (
            await db_session.execute(select(func.count(Report.id)).where(Report.project_id == project.id))
        ).scalar()
        assert report_count == 1

    @pytest.mark.asyncio
    async def test_enumerator_journey_completes_with_proofs(self, db_session, journey_setup):
        _, workflows = journey_setup
        run = await _execute_journey(db_session, workflows, "synthetic_enumerator_journey")

        assert run.status == WorkflowRunStatus.completed
        assert run.merkle_root and len(run.merkle_root) == 64
        proofs = (
            await db_session.execute(select(ValidationProof).where(ValidationProof.run_id == run.id))
        ).scalars().all()
        assert len(proofs) >= 3

        from app.models import SurveyResponse, ValidationStatusEnum

        project_id = run.output_data["create_offline_batch"]["result"]["project_id"]
        responses = (
            await db_session.execute(select(SurveyResponse).where(SurveyResponse.project_id == uuid.UUID(project_id)))
        ).scalars().all()
        # 6 offline rows captured, none lost during sync.
        assert len(responses) == 6
        assert all(r.submitted_via == "whatsapp" for r in responses)
        assert all("sync_provenance" in (r.responses or {}) for r in responses)
        # One duplicate household conflict was resolved (older row rejected).
        rejected = [r for r in responses if r.validation_status == ValidationStatusEnum.rejected]
        assert len(rejected) == 1
        assert run.output_data["sync_offline_batch"]["result"]["data_loss"] is False
        assert run.output_data["sync_offline_batch"]["result"]["conflicts_resolved"] == 1

    @pytest.mark.asyncio
    async def test_anomaly_journey_completes_with_proofs(self, db_session, journey_setup):
        _, workflows = journey_setup
        run = await _execute_journey(db_session, workflows, "synthetic_calc_anomaly_recovery")

        assert run.status == WorkflowRunStatus.completed
        assert run.merkle_root and len(run.merkle_root) == 64
        proofs = (
            await db_session.execute(select(ValidationProof).where(ValidationProof.run_id == run.id))
        ).scalars().all()
        assert len(proofs) >= 2

        output = run.output_data["inject_and_remediate_anomaly"]["result"]
        assert output["status"] == "resolved"
        assert output["attempts_used"] == 2  # first attempt failed, second succeeded
        assert output["after_state_hash"] and len(output["after_state_hash"]) == 64

        # The remediation path was exercised for real in the DB.
        attempts = (
            await db_session.execute(
                select(RemediationAttempt).where(RemediationAttempt.target_id == output["target_id"])
            )
        ).scalars().all()
        assert len(attempts) == 2
        assert any(a.status == "failed" for a in attempts)
        assert any(a.status == "resolved" for a in attempts)

        # No human escalation was created anywhere.
        escalations = (
            await db_session.execute(select(func.count(HumanEscalation.id)))
        ).scalar()
        events = (
            await db_session.execute(
                select(func.count(EscalationEvent.id)).where(
                    EscalationEvent.status != EscalationStatus.resolved
                )
            )
        ).scalar()
        assert escalations == 0
        assert events == 0


# ─── Runner (bounded) ─────────────────────────────────────────────────────────

class TestSyntheticRunner:
    @pytest.mark.asyncio
    async def test_runner_skips_inflight_journey(self, db_session, journey_setup, monkeypatch):
        _, workflows = journey_setup
        name = "synthetic_developer_journey"
        input_data = _journey_input()
        input_data["journey"] = name
        orchestrator = ValidationOrchestrator(db_session)
        await orchestrator.create_run(
            workflow_id=str(workflows[name].id),
            trigger_event="synthetic_test",
            input_data=input_data,
        )  # stays PENDING → in-flight

        assert await has_inflight_run(db_session, workflows[name].id, name) is True

        delayed: list[str] = []

        class _Stub:
            @staticmethod
            def delay(run_id: str):
                delayed.append(run_id)

        monkeypatch.setattr("app.validation_engine.tasks.execute_validation_run", _Stub)

        results = await run_synthetic_journeys(db_session)

        assert results[name]["status"] == "skipped"
        assert results[name]["reason"] == "in-flight run"
        # Other journeys still queued; the skipped journey never fired a delay.
        assert len(delayed) == 2
        for run_id in delayed:
            queued = await db_session.get(ValidationRun, uuid.UUID(run_id))
            assert queued.input_data.get("journey") != name

    @pytest.mark.asyncio
    async def test_runner_queues_journeys_and_appends_snapshot(
        self, db_session, journey_setup, monkeypatch
    ):
        await ensure_journey_workflows(db_session)

        delayed: list[str] = []

        class _Stub:
            @staticmethod
            def delay(run_id: str):
                delayed.append(run_id)

        monkeypatch.setattr("app.validation_engine.tasks.execute_validation_run", _Stub)

        results = await run_synthetic_journeys(db_session)

        assert len(delayed) == 3
        for name in get_journey_names():
            assert results[name]["status"] == "queued"
        snapshot_info = results["_health_snapshot"]
        assert 0 <= snapshot_info["score"] <= 100

        # A second pass skips everything (all three are now in flight).
        second = await run_synthetic_journeys(db_session)
        for name in get_journey_names():
            assert second[name]["status"] == "skipped"

        snapshots = (
            await db_session.execute(select(ValidationHealthSnapshot))
        ).scalars().all()
        assert len(snapshots) == 2


# ─── Health score math ────────────────────────────────────────────────────────

class TestHealthScoreMath:
    def test_perfect_health(self):
        stats = {name: {"completed": 5, "failed": 0} for name in get_journey_names()}
        assert compute_health_score(stats, None, 0) == 100

    def test_weighted_mix(self):
        stats = {"j1": {"completed": 3, "failed": 1}}  # 75%
        # 0.6*75 + 0.2*50 + 0.2*60 = 45 + 10 + 12
        assert compute_health_score(stats, 0.5, 2) == 67

    def test_no_runs_is_healthy(self):
        assert journey_success_percent({}) == 100.0
        assert compute_health_score({}, None, 0) == 100

    def test_escalation_backlog(self):
        assert escalation_backlog_percent(0) == 100.0
        assert escalation_backlog_percent(2) == 60.0
        assert escalation_backlog_percent(10) == 0.0

    def test_clamped_to_bounds(self):
        assert compute_health_score({"j": {"completed": 0, "failed": 9}}, 0.0, 50) == 0

    def test_streak_from_daily_scores(self):
        today = datetime.now(UTC).date()
        day = timedelta(days=1)

        # Seven consecutive below-threshold days ending today.
        scores = {today - i * day: 70 for i in range(7)}
        assert streak_from_daily_scores(scores) == 7

        # A healthy latest day resets the streak.
        scores[today] = 95
        assert streak_from_daily_scores(scores) == 0

        # Mixed pattern: only the trailing run counts.
        scores = {
            today: 70,
            today - day: 70,
            today - 2 * day: 95,
            today - 3 * day: 70,
        }
        assert streak_from_daily_scores(scores) == 2

        # Missing today → no evidence today is below threshold → 0.
        scores = {today - day: 70, today - 2 * day: 70}
        assert streak_from_daily_scores(scores) == 0

        # Empty history → 0.
        assert streak_from_daily_scores({}) == 0

    def test_utc_day_normalizes_naive_and_aware(self):
        today = datetime.now(UTC).date()
        assert utc_day(datetime.now(UTC)) == today
        assert utc_day(datetime.now(UTC).replace(tzinfo=None)) == today

    @pytest.mark.asyncio
    async def test_snapshot_streak_is_daily(self, db_session, journey_setup, monkeypatch):
        _, workflows = journey_setup

        # Yesterday was below threshold (seeded directly).
        await _seed_historical_snapshot(db_session, score=70, days_ago=1)

        forced: dict[str, int | None] = {"score": None}
        real_compute = compute_health_score
        monkeypatch.setattr(
            "app.validation_engine.health.compute_health_score",
            lambda *a, **k: forced["score"] if forced["score"] is not None else real_compute(*a, **k),
        )

        # Unhealthy: a failed remediation (0% resolution) plus an open escalation.
        # Journeys have no runs, which counts as neutral (100%).
        db_session.add(RemediationAttempt(
            rule_key="api_timeout_rate_limit",
            target_type="calculation",
            target_id="t-1",
            status="failed",
            attempt_number=1,
            before_state_hash="a" * 64,
        ))
        db_session.add(EscalationEvent(source="test", title="t", detail="d", priority=1))
        await db_session.commit()

        forced["score"] = 70
        bad = await compute_and_store_snapshot(db_session)
        assert bad.score < 90
        assert bad.consecutive_below_threshold == 2  # yesterday + today

        # A second below-threshold snapshot on the SAME UTC day does not
        # increment the streak — the counter is per day, not per snapshot.
        bad2 = await compute_and_store_snapshot(db_session)
        assert bad2.consecutive_below_threshold == 2

        # Healthy state: all journeys completed, remediation half-resolved,
        # escalation cleared. Score = 0.6*100 + 0.2*50 + 0.2*100 = 90.
        await _seed_journey_run(db_session, workflows, "synthetic_developer_journey", WorkflowRunStatus.completed)
        await _seed_journey_run(db_session, workflows, "synthetic_enumerator_journey", WorkflowRunStatus.completed)
        await _seed_journey_run(db_session, workflows, "synthetic_calc_anomaly_recovery", WorkflowRunStatus.completed)
        db_session.add(RemediationAttempt(
            rule_key="api_timeout_rate_limit",
            target_type="calculation",
            target_id="t-2",
            status="resolved",
            attempt_number=1,
            before_state_hash="b" * 64,
            after_state_hash="c" * 64,
        ))
        event_result = await db_session.execute(select(EscalationEvent))
        event = event_result.scalar_one()
        event.status = EscalationStatus.resolved
        await db_session.commit()

        # Even a >=90 snapshot later the SAME day does not reset: today's
        # daily score is the worst of the day's snapshots (70).
        forced["score"] = None
        same_day = await compute_and_store_snapshot(db_session)
        assert same_day.score >= 90
        assert same_day.consecutive_below_threshold == 2

        journey_stats = await compute_journey_stats(db_session)
        assert journey_stats["synthetic_developer_journey"] == {"completed": 1, "failed": 0}


# ─── Daily streak semantics (deploy gate) ─────────────────────────────────────

async def _seed_historical_snapshot(
    db_session: AsyncSession, score: int, days_ago: int, at_hour: int = 12
) -> ValidationHealthSnapshot:
    """Snapshot at noon ``days_ago`` days ago (deterministic, day-boundary safe)."""
    created = datetime.now(UTC) - timedelta(days=days_ago)
    snapshot = ValidationHealthSnapshot(
        score=score,
        run_stats={},
        consecutive_below_threshold=0,
        created_at=created.replace(hour=at_hour, minute=0, second=0, microsecond=0),
    )
    db_session.add(snapshot)
    await db_session.commit()
    return snapshot


class TestDailyStreak:
    @pytest.mark.asyncio
    async def test_daily_scores_take_worst_snapshot_of_day(self, db_session):
        await _seed_historical_snapshot(db_session, score=95, days_ago=1, at_hour=9)
        await _seed_historical_snapshot(db_session, score=50, days_ago=1, at_hour=15)
        await _seed_historical_snapshot(db_session, score=80, days_ago=2, at_hour=12)

        scores = await daily_scores(db_session)
        assert len(scores) == 2
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        day_before = (datetime.now(UTC) - timedelta(days=2)).date()
        assert scores[yesterday] == 50  # min(95, 50)
        assert scores[day_before] == 80

    @pytest.mark.asyncio
    async def test_seven_consecutive_bad_days_block(
        self, db_session, journey_setup, monkeypatch
    ):
        # Six prior days all below 90, plus a below-threshold snapshot today
        # → 7 consecutive daily scores < 90 (the deploy gate blocks at 7).
        for days_ago in range(1, 7):
            await _seed_historical_snapshot(db_session, score=70, days_ago=days_ago)

        monkeypatch.setattr(
            "app.validation_engine.health.compute_health_score",
            lambda *a, **k: 70,
        )
        snapshot = await compute_and_store_snapshot(db_session)
        assert snapshot.consecutive_below_threshold == 7

    @pytest.mark.asyncio
    async def test_healthy_day_resets_streak(
        self, db_session, journey_setup, monkeypatch
    ):
        # Seven prior days below 90, but today's first snapshot is healthy.
        for days_ago in range(1, 8):
            await _seed_historical_snapshot(db_session, score=70, days_ago=days_ago)

        monkeypatch.setattr(
            "app.validation_engine.health.compute_health_score",
            lambda *a, **k: 95,
        )
        snapshot = await compute_and_store_snapshot(db_session)
        assert snapshot.consecutive_below_threshold == 0

    @pytest.mark.asyncio
    async def test_mixed_pattern_counts_trailing_run_only(
        self, db_session, journey_setup, monkeypatch
    ):
        # day 3 ago: 70, day 2 ago: 70, day 1 ago: 95, today: 70 → streak 1.
        await _seed_historical_snapshot(db_session, score=70, days_ago=3)
        await _seed_historical_snapshot(db_session, score=70, days_ago=2)
        await _seed_historical_snapshot(db_session, score=95, days_ago=1)

        monkeypatch.setattr(
            "app.validation_engine.health.compute_health_score",
            lambda *a, **k: 70,
        )
        snapshot = await compute_and_store_snapshot(db_session)
        assert snapshot.consecutive_below_threshold == 1

    @pytest.mark.asyncio
    async def test_multiple_bad_snapshots_one_day_count_once(
        self, db_session, journey_setup, monkeypatch
    ):
        # Three below-threshold snapshots yesterday still count as one day.
        for at_hour in (9, 12, 15):
            await _seed_historical_snapshot(db_session, score=70, days_ago=1, at_hour=at_hour)

        monkeypatch.setattr(
            "app.validation_engine.health.compute_health_score",
            lambda *a, **k: 70,
        )
        snapshot = await compute_and_store_snapshot(db_session)
        assert snapshot.consecutive_below_threshold == 2  # yesterday + today


# ─── Deploy gate ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def gate_module():
    sys.path.insert(0, str(BACKEND_ROOT))
    try:
        yield importlib.import_module("scripts.pre_deploy_check")
    finally:
        sys.path.remove(str(BACKEND_ROOT))


_PASS_JOURNEYS = {
    "synthetic_developer_journey": {"completed": 3, "failed": 0},
    "synthetic_enumerator_journey": {"completed": 3, "failed": 0},
    "synthetic_calc_anomaly_recovery": {"completed": 3, "failed": 0},
}


def _snapshot_history(daily_scores: list[int]) -> list[dict]:
    """History of one noon snapshot per day, ending today (UTC)."""
    today = datetime.now(UTC).date()
    history = []
    for offset, score in enumerate(daily_scores):
        day = today - timedelta(days=len(daily_scores) - 1 - offset)
        history.append({"score": score, "created_at": f"{day.isoformat()}T12:00:00+00:00"})
    return history


def _validation_payload(daily_scores=None, journeys=None):
    history = _snapshot_history(daily_scores if daily_scores is not None else [95])
    return {
        "latest": history[-1],
        "history": history,
        "journeys": journeys if journeys is not None else _PASS_JOURNEYS,
    }


class TestDeployGate:
    def test_pass_case(self, gate_module):
        assert gate_module.evaluate_gate({"score": 95}, _validation_payload()) == []

    def test_block_low_score(self, gate_module):
        reasons = gate_module.evaluate_gate({"score": 80}, _validation_payload())
        assert any("below the required" in r for r in reasons)

    def test_block_streak(self, gate_module):
        # 7 consecutive days with daily (worst-of-day) score below 90.
        reasons = gate_module.evaluate_gate({"score": 95}, _validation_payload([70] * 7))
        assert any("consecutive days" in r for r in reasons)

    def test_streak_reset_by_healthy_day(self, gate_module):
        reasons = gate_module.evaluate_gate(
            {"score": 95}, _validation_payload([70, 70, 70, 70, 70, 70, 95])
        )
        assert not any("consecutive days" in r for r in reasons)

    def test_six_days_below_threshold_does_not_block(self, gate_module):
        reasons = gate_module.evaluate_gate({"score": 95}, _validation_payload([70] * 6))
        assert not any("consecutive days" in r for r in reasons)

    def test_block_failed_journey(self, gate_module):
        journeys = {**_PASS_JOURNEYS, "synthetic_enumerator_journey": {"completed": 1, "failed": 2}}
        reasons = gate_module.evaluate_gate({"score": 95}, _validation_payload(journeys=journeys))
        assert any("synthetic_enumerator_journey" in r and "failed" in r for r in reasons)

    def test_block_journey_without_completions(self, gate_module):
        journeys = {**_PASS_JOURNEYS, "synthetic_calc_anomaly_recovery": {"completed": 0, "failed": 0}}
        reasons = gate_module.evaluate_gate({"score": 95}, _validation_payload(journeys=journeys))
        assert any("no completed runs" in r for r in reasons)

    def test_block_missing_payloads(self, gate_module):
        reasons = gate_module.evaluate_gate(None, None)
        assert any("no validation health snapshots" in r for r in reasons)
        assert any("no synthetic journey runs" in r for r in reasons)

    def test_main_pass_and_block_exit_codes(self, gate_module, monkeypatch):
        monkeypatch.setattr(
            gate_module,
            "fetch_json",
            lambda client, base, path, token: {"score": 95}
            if "escalations" in path
            else _validation_payload(),
        )
        assert gate_module.main(["--base-url", "http://unused"]) == 0

        monkeypatch.setattr(
            gate_module,
            "fetch_json",
            lambda client, base, path, token: {"score": 50}
            if "escalations" in path
            else _validation_payload(),
        )
        assert gate_module.main(["--base-url", "http://unused"]) == 1

    def test_offline_selftest_subprocess_exit_code(self):
        result = subprocess.run(
            [sys.executable, str(BACKEND_ROOT / "scripts" / "pre_deploy_check.py"), "--offline-selftest"],
            capture_output=True,
            text=True,
            cwd=str(BACKEND_ROOT),
            timeout=60,
            check=False,
        )
        assert result.returncode == 0
        assert "all gate cases passed" in result.stdout


# ─── Service-level sanity ─────────────────────────────────────────────────────

class TestJourneyService:
    @pytest.mark.asyncio
    async def test_assert_true(self, db_session, patch_db_context):
        ok = await journey_service.assert_true(True, "should pass")
        assert ok["passed"] is True
        with pytest.raises(RuntimeError, match="assertion_failed"):
            await journey_service.assert_true(False, "should fail")
