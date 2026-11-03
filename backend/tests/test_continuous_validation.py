"""Continuous validation: synthetic journeys, health snapshots, deploy gate.

Hermetic: SQLite in-memory, no network (Radix anchoring is simulated because
RADIX_ENABLED defaults to False), no real sleeping (ENVIRONMENT=test gives the
remediation engine a no-op sleeper).
"""

import importlib
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.escalations.models import EscalationEvent, EscalationStatus
from app.remediation.models import RemediationAttempt
from app.validation_engine.health import (
    compute_health_score,
    compute_journey_stats,
    escalation_backlog_percent,
    journey_success_percent,
    next_streak,
    compute_and_store_snapshot,
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
from app.tasks.validation_jobs import has_inflight_run, run_synthetic_journeys

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

    def test_next_streak(self):
        assert next_streak(3, 85) == 4
        assert next_streak(3, 90) == 0
        assert next_streak(None, 89) == 1
        assert next_streak(6, 100) == 0

    @pytest.mark.asyncio
    async def test_snapshot_streak_increment_and_reset(self, db_session, journey_setup):
        _, workflows = journey_setup

        async def _seed_run(name: str, status: WorkflowRunStatus):
            run = ValidationRun(
                workflow_id=workflows[name].id,
                trigger_event="synthetic_test",
                status=status,
                input_data={"journey": name, "synthetic": True},
            )
            db_session.add(run)
            await db_session.commit()

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

        bad = await compute_and_store_snapshot(db_session)
        assert bad.score < 90
        assert bad.consecutive_below_threshold == 1
        bad2 = await compute_and_store_snapshot(db_session)
        assert bad2.consecutive_below_threshold == 2

        # Healthy pass: all journeys completed, remediation half-resolved,
        # escalation cleared. Score = 0.6*100 + 0.2*50 + 0.2*100 = 90 → reset.
        await _seed_run("synthetic_developer_journey", WorkflowRunStatus.completed)
        await _seed_run("synthetic_enumerator_journey", WorkflowRunStatus.completed)
        await _seed_run("synthetic_calc_anomaly_recovery", WorkflowRunStatus.completed)
        resolved = RemediationAttempt(
            rule_key="api_timeout_rate_limit",
            target_type="calculation",
            target_id="t-2",
            status="resolved",
            attempt_number=1,
            before_state_hash="b" * 64,
            after_state_hash="c" * 64,
        )
        db_session.add(resolved)
        event_result = await db_session.execute(select(EscalationEvent))
        event = event_result.scalar_one()
        event.status = EscalationStatus.resolved
        await db_session.commit()

        good = await compute_and_store_snapshot(db_session)
        assert good.score >= 90
        assert good.consecutive_below_threshold == 0

        journey_stats = await compute_journey_stats(db_session)
        assert journey_stats["synthetic_developer_journey"] == {"completed": 1, "failed": 0}


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


def _validation_payload(streak: int = 0, journeys=None):
    return {
        "latest": {"score": 95, "consecutive_below_threshold": streak},
        "history": [],
        "journeys": journeys if journeys is not None else _PASS_JOURNEYS,
    }


class TestDeployGate:
    def test_pass_case(self, gate_module):
        assert gate_module.evaluate_gate({"score": 95}, _validation_payload()) == []

    def test_block_low_score(self, gate_module):
        reasons = gate_module.evaluate_gate({"score": 80}, _validation_payload())
        assert any("below the required" in r for r in reasons)

    def test_block_streak(self, gate_module):
        reasons = gate_module.evaluate_gate({"score": 95}, _validation_payload(streak=7))
        assert any("consecutive snapshots" in r for r in reasons)

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
