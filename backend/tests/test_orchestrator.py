"""Tests for Kimi Claw multi-agent orchestration system."""

import uuid
import asyncio
import pytest
from datetime import datetime, timedelta

from app.models import ProjectStatusEnum
from app.agents.base import AgentResult
from app.agents import (
    IngestionAgent,
    ValidationAgent,
    CalculationAgent,
    ReportingAgent,
    VVBLiaisonAgent,
    QualityControlAgent,
    ClientSuccessAgent,
    AGENT_REGISTRY,
)
from app.orchestrator.orchestrator import KimiClawOrchestrator, STATE_TRANSITIONS, TRIGGER_STATES
from app.orchestrator.events import EventLogger
from app.services.kimi_api import KimiAPIClient


def _run_async(coro):
    """Helper to run async coroutines in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─── Mock Database ────────────────────────────────────────────────────────────

class MockResult:
    def __init__(self, scalar_val=None, scalars_val=None):
        self._scalar = scalar_val
        self._scalars = scalars_val or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar(self):
        return self._scalar

    def scalars(self):
        class MockScalars:
            def __init__(self, items):
                self.items = items
            def all(self):
                return self.items
        return MockScalars(self._scalars)


class MockSession:
    def __init__(self):
        self.committed = []
        self.refreshed = []

    async def execute(self, stmt):
        return MockResult()

    async def commit(self):
        pass

    async def refresh(self, obj):
        self.refreshed.append(obj)
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid.uuid4()

    def add(self, obj):
        self.committed.append(obj)
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid.uuid4()


# ─── Agent Unit Tests ─────────────────────────────────────────────────────────

class TestAgentResult:
    def test_confidence_clamping(self):
        r = AgentResult(status="completed", confidence_score=1.5, output_data={})
        assert r.confidence_score == 1.0

        r2 = AgentResult(status="completed", confidence_score=-0.5, output_data={})
        assert r2.confidence_score == 0.0

    def test_to_dict(self):
        r = AgentResult(
            status="completed",
            confidence_score=0.92,
            output_data={"key": "value"},
            errors=["err"],
            execution_time_ms=150,
        )
        d = r.to_dict()
        assert d["status"] == "completed"
        assert d["confidence_score"] == 0.92
        assert d["execution_time_ms"] == 150


class TestAgentRegistry:
    def test_all_agents_registered(self):
        expected = [
            "ingestion", "validation", "calculation", "reporting",
            "vvb_liaison", "quality_control", "client_success",
        ]
        for name in expected:
            assert name in AGENT_REGISTRY


class TestIngestionAgent:
    def test_no_pending_uploads(self):
        agent = IngestionAgent(project_id=uuid.uuid4(), db_session=MockSession())
        result = _run_async(agent.run({}))
        assert result.status == "completed"
        assert result.confidence_score == 1.0
        assert result.output_data["processed_count"] == 0


class TestValidationAgent:
    def test_no_data_sources(self):
        agent = ValidationAgent(project_id=uuid.uuid4(), db_session=MockSession())
        result = _run_async(agent.run({}))
        assert result.status == "completed"
        assert result.confidence_score == 0.0
        assert "No data sources" in result.errors[0]


class TestCalculationAgent:
    def test_project_not_found(self):
        agent = CalculationAgent(project_id=uuid.uuid4(), db_session=MockSession())
        result = _run_async(agent.run({}))
        assert result.status == "failed"
        assert result.confidence_score == 0.0


class TestReportingAgent:
    def test_project_not_found(self):
        agent = ReportingAgent(project_id=uuid.uuid4(), db_session=MockSession())
        result = _run_async(agent.run({}))
        assert result.status == "failed"
        assert result.confidence_score == 0.0


class TestVVBLiaisonAgent:
    def test_project_not_found(self):
        agent = VVBLiaisonAgent(project_id=uuid.uuid4(), db_session=MockSession())
        result = _run_async(agent.run({}))
        assert result.status == "failed"
        assert result.confidence_score == 0.0


class TestQualityControlAgent:
    def test_always_completes(self):
        agent = QualityControlAgent(project_id=uuid.uuid4(), db_session=MockSession())
        result = _run_async(agent.run({"check_type": "milestone"}))
        assert result.status == "completed"
        assert "flag_count" in result.output_data
        assert "severity" in result.output_data


class TestClientSuccessAgent:
    def test_project_not_found(self):
        agent = ClientSuccessAgent(project_id=uuid.uuid4(), db_session=MockSession())
        result = _run_async(agent.run({}))
        assert result.status == "failed"
        assert result.confidence_score == 0.0


# ─── Orchestrator Tests ───────────────────────────────────────────────────────

class TestStateMachine:
    def test_state_transitions_defined(self):
        assert ProjectStatusEnum.onboarding in STATE_TRANSITIONS
        assert ProjectStatusEnum.data_collection in STATE_TRANSITIONS
        assert ProjectStatusEnum.calculation in STATE_TRANSITIONS
        assert ProjectStatusEnum.review in STATE_TRANSITIONS
        assert ProjectStatusEnum.submitted in STATE_TRANSITIONS
        assert ProjectStatusEnum.verified in STATE_TRANSITIONS
        assert ProjectStatusEnum.monitoring in STATE_TRANSITIONS

    def test_trigger_states_mapping(self):
        assert TRIGGER_STATES["data_complete"] == ProjectStatusEnum.data_collection
        assert TRIGGER_STATES["validation_passed"] == ProjectStatusEnum.calculation
        assert TRIGGER_STATES["calculation_complete"] == ProjectStatusEnum.review
        assert TRIGGER_STATES["report_approved"] == ProjectStatusEnum.submitted
        assert TRIGGER_STATES["registry_approved"] == ProjectStatusEnum.verified


class TestOrchestratorLogic:
    def test_process_project_not_found(self):
        orch = KimiClawOrchestrator(MockSession())
        result = _run_async(orch.process_project(uuid.uuid4(), "data_complete"))
        assert "error" in result
        assert result["error"] == "Project not found"

    def test_dispatch_unknown_agent(self):
        orch = KimiClawOrchestrator(MockSession())
        result = _run_async(orch.dispatch_agent(
            project_id=uuid.uuid4(),
            agent_type="nonexistent",
            trigger_event="test",
            context={},
        ))
        assert result.status == "failed"
        assert "Unknown agent type" in result.errors[0]

    def test_confidence_tier(self):
        from app.agents.base import BaseAgent
        # Create a concrete subclass for testing
        class TestAgent(BaseAgent):
            agent_type = "test"
            async def run(self, context):
                return AgentResult(status="completed", confidence_score=1.0, output_data={})

        agent = TestAgent(uuid.uuid4())
        assert agent._compute_confidence_tier(0.96) == "auto_advance"
        assert agent._compute_confidence_tier(0.95) == "auto_advance"
        assert agent._compute_confidence_tier(0.90) == "human_review"
        assert agent._compute_confidence_tier(0.85) == "human_review"
        assert agent._compute_confidence_tier(0.84) == "escalate"
        assert agent._compute_confidence_tier(0.50) == "escalate"

    def test_get_next_trigger(self):
        orch = KimiClawOrchestrator.__new__(KimiClawOrchestrator)
        assert orch._get_next_trigger("ingestion") == "data_complete"
        assert orch._get_next_trigger("validation") == "validation_passed"
        assert orch._get_next_trigger("calculation") == "calculation_complete"
        assert orch._get_next_trigger("reporting") == "report_approved"
        assert orch._get_next_trigger("vvb_liaison") == "registry_approved"
        assert orch._get_next_trigger("unknown") is None

    def test_suggest_action(self):
        orch = KimiClawOrchestrator.__new__(KimiClawOrchestrator)
        result = AgentResult(status="completed", confidence_score=0.9, output_data={})
        action = orch._suggest_action("ingestion", result)
        assert "Review" in action

        result_low = AgentResult(status="completed", confidence_score=0.7, output_data={}, errors=[])
        action_low = orch._suggest_action("ingestion", result_low)
        assert "low confidence" in action_low


# ─── Event Logger Tests ───────────────────────────────────────────────────────

class TestEventLogger:
    def test_log_state_transition(self):
        logger = EventLogger(MockSession())
        event = _run_async(logger.log_state_transition(
            project_id=uuid.uuid4(),
            from_state="onboarding",
            to_state="data_collection",
        ))
        assert event.event_type.value == "state_transition"
        assert event.from_state == "onboarding"
        assert event.to_state == "data_collection"


# ─── Kimi API Client Tests ────────────────────────────────────────────────────

class TestKimiAPIClient:
    def test_fallback_response(self):
        client = KimiAPIClient(api_key="")
        result = client._fallback_response([{"role": "user", "content": "Test query"}])
        assert result["success"] is False
        assert "fallback" in result["content"]

    def test_fallback_with_empty_messages(self):
        client = KimiAPIClient(api_key="")
        result = client._fallback_response([])
        assert result["success"] is False

    def test_draft_vvb_response_no_key(self):
        client = KimiAPIClient(api_key="")
        result = _run_async(client.draft_vvb_response(
            query_text="Why is fNRB 0.3?",
            project_data={"name": "Test", "methodology": "TPDDTEC_v4"},
        ))
        assert "fallback" in result or "fNRB" in result

    def test_generate_executive_summary_no_key(self):
        client = KimiAPIClient(api_key="")
        result = _run_async(client.generate_executive_summary(
            project_data={"name": "Test", "methodology": "TPDDTEC_v4"},
            calculation_results={"emissions_reduction_tco2e": 5000},
        ))
        assert "fallback" in result or "tCO2e" in result

    def test_answer_methodology_question_no_key(self):
        client = KimiAPIClient(api_key="")
        result = _run_async(client.answer_methodology_question(
            question="What is fNRB?",
            methodology="TPDDTEC_v4",
        ))
        assert "fallback" in result or "fNRB" in result

    def test_explain_anomaly_no_key(self):
        client = KimiAPIClient(api_key="")
        result = _run_async(client.explain_anomaly(
            data_point={"value": 999, "expected": 100},
            field_name="value",
        ))
        assert "fallback" in result or "anomalous" in result
