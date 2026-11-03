"""Tests for agent autonomy: real-data reasoning, LLM fallback, explainability."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.agents import (
    AGENT_REGISTRY,
    CalculationAgent,
    ClientSuccessAgent,
    IngestionAgent,
    QualityControlAgent,
    ReportingAgent,
    ValidationAgent,
    VVBLiaisonAgent,
)
from app.agents.base import AgentResult, BaseAgent, BLEND_FORMULA
from app.models import (
    CalculationRun,
    CalculationStatusEnum,
    DataSource,
    DetectedFileTypeEnum,
    Developer,
    FileUpload,
    FileUploadStatusEnum,
    MethodologyEnum,
    Project,
    ProjectStatusEnum,
    Report,
    ReportStatusEnum,
    ReportTemplateTypeEnum,
    SourceTypeEnum,
    SupportTicket,
    SurveyResponse,
    User,
    UserRoleEnum,
    ValidationStatusEnum,
    WhatsAppConversation,
    AgentDecision,
)
from app.core.encryption import compute_searchable_hash


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_project(db_session):
    """Project with owner developer account."""
    email = f"owner-{uuid.uuid4().hex[:8]}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Owner User",
        role=UserRoleEnum.developer,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.commit()

    developer = Developer(id=uuid.uuid4(), user_id=user.id, company_name="Acme Carbon")
    db_session.add(developer)
    await db_session.commit()

    project = Project(
        id=uuid.uuid4(),
        name="Autonomy Test Project",
        developer_id=developer.id,
        methodology=MethodologyEnum.TPDDTEC_v4,
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        status=ProjectStatusEnum.data_collection,
        complexity_score=0.72,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def seeded_calc_run(db_session, seeded_project):
    calc = CalculationRun(
        id=uuid.uuid4(),
        project_id=seeded_project.id,
        monitoring_period_start=date(2024, 1, 1),
        monitoring_period_end=date(2024, 12, 31),
        fNRB_value=0.31,
        emissions_reduction_tCO2e=5200.0,
        uncertainty_95CI=400.0,
        leakage_assessment={"total_leakage_tco2e": 120.0},
        methodology_compliance_score=88.0,
        status=CalculationStatusEnum.draft,
    )
    db_session.add(calc)
    await db_session.commit()
    await db_session.refresh(calc)
    return calc


def _make_upload(project_id, filename, file_hash, status=FileUploadStatusEnum.completed, **kwargs):
    return FileUpload(
        id=uuid.uuid4(),
        project_id=project_id,
        original_filename=filename,
        detected_type=kwargs.pop("detected_type", DetectedFileTypeEnum.excel),
        mime_type=kwargs.pop("mime_type", "application/vnd.ms-excel"),
        s3_key=kwargs.pop("s3_key", f"uploads/{filename}"),
        s3_bucket=kwargs.pop("s3_bucket", "test-bucket"),
        file_size_bytes=kwargs.pop("file_size_bytes", 1024),
        file_hash_sha256=file_hash,
        status=status,
        **kwargs,
    )


def _assert_explainable(result):
    """Common explainability assertions for every agent result."""
    assert 0.0 <= result.confidence_score <= 1.0
    assert result.reasoning, "reasoning must be non-empty"
    assert isinstance(result.evidence, dict)
    assert result.output_data["reasoning"] == result.reasoning
    assert result.output_data["evidence"] == result.evidence
    assert result.execution_time_ms is None or result.execution_time_ms >= 0


# ─── BaseAgent helpers ────────────────────────────────────────────────────────

class TestBlendConfidence:
    def test_blend_with_llm(self):
        class _A(BaseAgent):
            agent_type = "t"
            async def run(self, context):
                return AgentResult("completed", 1.0, {})

        agent = _A(uuid.uuid4())
        assert agent.blend_confidence(0.5, 1.0) == pytest.approx(0.5 * 0.4 + 1.0 * 0.6)
        assert agent.blend_confidence(1.0, 0.0) == pytest.approx(0.4)

    def test_blend_without_llm(self):
        class _A(BaseAgent):
            agent_type = "t"
            async def run(self, context):
                return AgentResult("completed", 1.0, {})

        agent = _A(uuid.uuid4())
        assert agent.blend_confidence(0.73) == 0.73

    def test_blend_clamps_inputs(self):
        class _A(BaseAgent):
            agent_type = "t"
            async def run(self, context):
                return AgentResult("completed", 1.0, {})

        agent = _A(uuid.uuid4())
        assert agent.blend_confidence(1.5, 2.0) == 1.0
        assert agent.blend_confidence(-1.0, -1.0) == 0.0

    def test_tier_boundaries_unchanged(self):
        class _A(BaseAgent):
            agent_type = "t"
            async def run(self, context):
                return AgentResult("completed", 1.0, {})

        agent = _A(uuid.uuid4())
        assert agent._compute_confidence_tier(0.95) == "auto_advance"
        assert agent._compute_confidence_tier(0.85) == "human_review"
        assert agent._compute_confidence_tier(0.84) == "escalate"

    def test_blend_formula_documented(self):
        assert "0.4" in BLEND_FORMULA and "0.6" in BLEND_FORMULA


# ─── Per-agent autonomy tests (no KIMI_API_KEY → fallback path, no network) ───

class TestIngestionAgentAutonomy:
    @pytest.mark.asyncio
    async def test_empty_project_no_exceptions(self, db_session, seeded_project):
        result = await IngestionAgent(seeded_project.id, db_session).execute("test", {})
        assert result.status == "completed"
        assert 0.5 <= result.confidence_score <= 0.7
        _assert_explainable(result)

    @pytest.mark.asyncio
    async def test_flags_duplicate_and_out_of_range(self, db_session, seeded_project):
        shared_hash = "a" * 64
        db_session.add_all([
            _make_upload(seeded_project.id, "baseline.xlsx", shared_hash),
            _make_upload(seeded_project.id, "baseline-copy.xlsx", shared_hash),
            _make_upload(seeded_project.id, "survey.csv", "b" * 64),
        ])
        db_session.add(DataSource(
            id=uuid.uuid4(),
            project_id=seeded_project.id,
            source_type=SourceTypeEnum.mobile_survey,
            schema_version="v1",
            processed_data={"records_extracted": 150, "fields_mapped": 12, "fuel_kg_per_day": -5},
            validation_status=ValidationStatusEnum.valid,
            confidence_score=0.9,
        ))
        await db_session.commit()

        result = await IngestionAgent(seeded_project.id, db_session).execute("test", {})
        _assert_explainable(result)
        evidence = result.evidence
        assert evidence["upload_count"] == 3
        assert evidence["anomaly_count"] >= 2  # duplicate + negative value
        anomaly_types = {a["type"] for a in evidence["anomalies"]}
        assert "duplicate_upload" in anomaly_types
        assert "out_of_range_value" in anomaly_types
        assert "duplicate" in result.reasoning.lower() or "out of plausible range" in result.reasoning


class TestCalculationAgentAutonomy:
    @pytest.mark.asyncio
    async def test_empty_project_no_exceptions(self, db_session, seeded_project):
        result = await CalculationAgent(seeded_project.id, db_session).execute("test", {})
        assert result.status in ("completed", "queued_for_review")
        _assert_explainable(result)
        # Reasoning cites each engine result.
        for token in ("fNRB", "leakage", "uncertainty", "methodology"):
            assert token in result.reasoning

    @pytest.mark.asyncio
    async def test_evidence_cites_engines(self, db_session, seeded_project):
        db_session.add(DataSource(
            id=uuid.uuid4(),
            project_id=seeded_project.id,
            source_type=SourceTypeEnum.mobile_survey,
            schema_version="v1",
            processed_data={"records_extracted": 150},
            validation_status=ValidationStatusEnum.valid,
        ))
        await db_session.commit()

        result = await CalculationAgent(seeded_project.id, db_session).execute("test", {})
        _assert_explainable(result)
        assert result.evidence["fnrb_value"] is not None
        assert "baseline_emissions_tco2e_per_year" in result.evidence
        assert "calculation_run_id" in result.output_data


class TestReportingAgentAutonomy:
    @pytest.mark.asyncio
    async def test_no_calc_run_graceful(self, db_session, seeded_project):
        result = await ReportingAgent(seeded_project.id, db_session).execute("test", {})
        assert result.status == "completed"
        assert 0.5 <= result.confidence_score <= 0.7
        _assert_explainable(result)

    @pytest.mark.asyncio
    async def test_generates_report_with_reasoning(self, db_session, seeded_project, seeded_calc_run, monkeypatch):
        # WeasyPrint native libs are not guaranteed in CI; stub only the PDF step.
        monkeypatch.setattr(
            "app.reports.generator.html_to_pdf",
            lambda html, path: path,
        )
        db_session.add(DataSource(
            id=uuid.uuid4(),
            project_id=seeded_project.id,
            source_type=SourceTypeEnum.satellite,
            schema_version="v1",
            processed_data={"records_extracted": 42},
            validation_status=ValidationStatusEnum.valid,
        ))
        await db_session.commit()

        result = await ReportingAgent(seeded_project.id, db_session).execute("test", {})
        _assert_explainable(result)
        assert "report_id" in result.output_data
        assert "quality_gates" in result.evidence or "gate_pass_rate" in result.evidence
        assert "quality gates" in result.reasoning or "Quality gates" in result.reasoning


class TestVVBLiaisonAgentAutonomy:
    @pytest.mark.asyncio
    async def test_no_report_graceful(self, db_session, seeded_project):
        result = await VVBLiaisonAgent(seeded_project.id, db_session).execute("test", {})
        assert result.status == "completed"
        assert 0.5 <= result.confidence_score <= 0.7
        _assert_explainable(result)

    @pytest.mark.asyncio
    async def test_drafts_vvb_responses(self, db_session, seeded_project, seeded_calc_run):
        report = Report(
            id=uuid.uuid4(),
            project_id=seeded_project.id,
            calculation_run_id=seeded_calc_run.id,
            template_type=ReportTemplateTypeEnum.GoldStandard_TPDDTEC,
            status=ReportStatusEnum.submitted,
            draft_content={"quality_gates": {"passed": True}},
            vvb_feedback={"queries": ["What is the source of the fNRB value?", "Unknown zzq question?"]},
        )
        db_session.add(report)
        await db_session.commit()

        result = await VVBLiaisonAgent(seeded_project.id, db_session).execute("test", {})
        _assert_explainable(result)
        responses = result.output_data["responses"]
        assert len(responses) == 2
        categories = {r["category"] for r in responses}
        assert "fnrb_source" in categories
        sources = {r["source"] for r in responses}
        assert "knowledge_base" in sources
        # Unclassifiable query escalated to Kimi draft (fallback text, no network).
        assert "kimi_draft" in sources
        assert result.evidence["answered_count"] == 2
        assert result.evidence["registry"] == "gold_standard"


class TestQualityControlAgentAutonomy:
    @pytest.mark.asyncio
    async def test_empty_project_no_exceptions(self, db_session, seeded_project):
        result = await QualityControlAgent(seeded_project.id, db_session).execute("milestone", {})
        assert result.status == "completed"
        _assert_explainable(result)
        assert "skipped" in result.evidence["cross_project"]

    @pytest.mark.asyncio
    async def test_iqr_outlier_detected(self, db_session, seeded_project):
        base = datetime.now(timezone.utc) - timedelta(days=1)
        for i, emissions in enumerate([100.0, 101.0, 99.0, 100.5, 9000.0]):
            db_session.add(CalculationRun(
                id=uuid.uuid4(),
                project_id=seeded_project.id,
                monitoring_period_start=date(2024, 1, 1),
                monitoring_period_end=date(2024, 12, 31),
                emissions_reduction_tCO2e=emissions,
                fNRB_value=0.3,
                uncertainty_95CI=10.0,
                status=CalculationStatusEnum.draft,
                created_at=base + timedelta(hours=i),
            ))
        await db_session.commit()

        result = await QualityControlAgent(seeded_project.id, db_session).execute("milestone", {})
        _assert_explainable(result)
        assert result.evidence["outlier_count"] >= 1
        assert result.evidence["outlier_values"]
        assert result.evidence["sample_size"] >= 5


class TestValidationAgentAutonomy:
    @pytest.mark.asyncio
    async def test_empty_project_no_exceptions(self, db_session, seeded_project):
        result = await ValidationAgent(seeded_project.id, db_session).execute("test", {})
        assert result.status == "completed"
        assert 0.5 <= result.confidence_score <= 0.7
        _assert_explainable(result)

    @pytest.mark.asyncio
    async def test_red_flags_cap_confidence(self, db_session, seeded_project):
        # Three sources with identical record counts → implausibly smooth data.
        for i in range(3):
            db_session.add(DataSource(
                id=uuid.uuid4(),
                project_id=seeded_project.id,
                source_type=SourceTypeEnum.mobile_survey,
                schema_version="v1",
                processed_data={"records_extracted": 200, "fields_mapped": 12},
                validation_status=ValidationStatusEnum.valid,
            ))
        await db_session.commit()

        result = await ValidationAgent(seeded_project.id, db_session).execute("test", {})
        _assert_explainable(result)
        assert result.evidence["confidence_capped"] is True
        assert result.confidence_score <= 0.9
        flag_ids = {f["id"] for f in result.evidence["red_flags_raised"]}
        assert "smooth_activity_data" in flag_ids
        assert "smooth" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_additionality_screen_runs(self, db_session, seeded_project):
        db_session.add(DataSource(
            id=uuid.uuid4(),
            project_id=seeded_project.id,
            source_type=SourceTypeEnum.manual_entry,
            schema_version="v1",
            processed_data={"records_extracted": 10, "fields_mapped": 8},
            validation_status=ValidationStatusEnum.valid,
        ))
        await db_session.commit()

        result = await ValidationAgent(seeded_project.id, db_session).execute("test", {})
        _assert_explainable(result)
        additionality = result.evidence["additionality"]
        assert additionality["score"] > 0
        check_names = {c["check"] for c in additionality["checks"]}
        assert "crediting_period_order" in check_names
        assert "methodology_supported" in check_names


class TestClientSuccessAgentAutonomy:
    @pytest.mark.asyncio
    async def test_project_not_found(self, db_session):
        result = await ClientSuccessAgent(uuid.uuid4(), db_session).execute("test", {})
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_churn_risk_and_message(self, db_session, seeded_project):
        conv = WhatsAppConversation(
            id=uuid.uuid4(),
            project_id=seeded_project.id,
            phone_number="+254700000001",
        )
        db_session.add(conv)
        await db_session.flush()
        db_session.add(SurveyResponse(
            id=uuid.uuid4(),
            project_id=seeded_project.id,
            conversation_id=conv.id,
            confidence_score=0.8,
        ))
        db_session.add(SupportTicket(
            id=uuid.uuid4(),
            project_id=seeded_project.id,
            conversation_id=conv.id,
            phone_number="+254700000001",
            issue_type="data",
            description="help",
            status="open",
        ))
        await db_session.commit()

        result = await ClientSuccessAgent(seeded_project.id, db_session).execute("milestone", {})
        _assert_explainable(result)
        assert "churn_risk" in result.evidence
        assert "client_update_message" in result.output_data
        assert result.output_data["client_update_message"]["body"]
        assert result.evidence["survey_response_rate"] == 1.0
        assert result.evidence["open_tickets"] == 1
        assert result.evidence["owner_present"] is True


# ─── Orchestrator decision recording prefers AgentResult.reasoning ────────────

class TestDecisionReasoningWiring:
    @pytest.mark.asyncio
    async def test_decision_uses_agent_reasoning(self, db_session, seeded_project, monkeypatch):
        import app.orchestrator.orchestrator as orchestrator_module
        from app.orchestrator.orchestrator import KimiClawOrchestrator
        from sqlalchemy import select as sa_select

        agent_reasoning = "Duplicate upload detected in baseline data — review required."

        class ReasoningFakeAgent:
            def __init__(self, project_id, db_session=None):
                self.project_id = project_id
                self.db = db_session

            async def execute(self, trigger_event, context):
                return AgentResult(
                    status="completed",
                    confidence_score=0.9,  # human_review tier
                    output_data={"processed_count": 2},
                    execution_time_ms=5,
                    reasoning=agent_reasoning,
                    evidence={"anomaly_count": 1},
                )

        monkeypatch.setitem(
            orchestrator_module.AGENT_REGISTRY, "ingestion", ReasoningFakeAgent
        )

        orchestrator = KimiClawOrchestrator(db_session)
        result = await orchestrator.dispatch_agent(
            seeded_project.id, "ingestion", "data_complete", {}
        )
        assert result.reasoning == agent_reasoning

        decision_result = await db_session.execute(
            sa_select(AgentDecision).where(
                AgentDecision.project_id == seeded_project.id,
                AgentDecision.agent_type == "ingestion",
            )
        )
        decision = decision_result.scalars().first()
        assert decision is not None
        assert agent_reasoning in decision.reasoning
        assert "Confidence 0.90 maps to tier 'human_review'" in decision.reasoning

    def test_decision_reasoning_fallback_without_agent_reasoning(self):
        from app.orchestrator.orchestrator import KimiClawOrchestrator

        result = AgentResult(
            status="completed",
            confidence_score=0.9,
            output_data={"processed_count": 2},
        )
        text = KimiClawOrchestrator._decision_reasoning(
            "ingestion", uuid.uuid4(), result, "human_review"
        )
        assert "finished with status" in text  # composed fallback text


# ─── Kimi client tool-calling ─────────────────────────────────────────────────

class TestKimiToolCalling:
    @pytest.mark.asyncio
    async def test_chat_with_tools_parses_tool_calls(self, monkeypatch):
        from app.services.kimi_api import KimiAPIClient, ToolCallResult

        client = KimiAPIClient(api_key="test-key")

        class _FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {
                            "finish_reason": "tool_calls",
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "submit_result",
                                            "arguments": '{"anomaly_severity": 0.3, "summary": "ok"}',
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                    "usage": {"total_tokens": 42},
                }

        class _FakeHTTPClient:
            async def post(self, *args, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(client, "client", _FakeHTTPClient())

        result = await client.chat_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        )
        assert isinstance(result, ToolCallResult)
        assert result.finish_reason == "tool_reasoning" or result.finish_reason == "tool_calls"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "submit_result"
        assert result.tool_calls[0].arguments == {"anomaly_severity": 0.3, "summary": "ok"}

    @pytest.mark.asyncio
    async def test_reason_forces_submit_result_tool(self, monkeypatch):
        from app.services.kimi_api import KimiAPIClient

        client = KimiAPIClient(api_key="test-key")
        captured = {}

        class _FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {
                            "finish_reason": "tool_calls",
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "submit_result",
                                            "arguments": '{"plausibility": 0.9, "rationale": "consistent"}',
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                    "usage": {},
                }

        class _FakeHTTPClient:
            async def post(self, url, headers=None, json=None):
                captured["payload"] = json
                return _FakeResponse()

        monkeypatch.setattr(client, "client", _FakeHTTPClient())

        schema = {
            "type": "object",
            "properties": {
                "plausibility": {"type": "number"},
                "rationale": {"type": "string"},
            },
            "required": ["plausibility", "rationale"],
        }
        out = await client.reason(
            prompt="Check plausibility",
            context={"x": 1},
            response_schema=schema,
        )
        assert out == {"plausibility": 0.9, "rationale": "consistent"}
        # tool_choice forced to the submit_result tool, schema appended to tools.
        assert captured["payload"]["tool_choice"] == {
            "type": "function",
            "function": {"name": "submit_result"},
        }
        tool_names = [t["function"]["name"] for t in captured["payload"]["tools"]]
        assert "submit_result" in tool_names

    @pytest.mark.asyncio
    async def test_reason_fallback_without_network(self, monkeypatch):
        """No API key → deterministic _fallback result, no HTTP attempted."""
        from app.services.kimi_api import KimiAPIClient

        client = KimiAPIClient(api_key="")

        class _ExplodingHTTPClient:
            async def post(self, *args, **kwargs):
                raise AssertionError("network must not be touched without an API key")

        monkeypatch.setattr(client, "client", _ExplodingHTTPClient())

        out = await client.reason(
            prompt="Assess anomalies",
            context={"uploads": 3},
            response_schema={
                "type": "object",
                "properties": {"anomaly_severity": {"type": "number"}},
                "required": ["anomaly_severity"],
            },
        )
        assert out["_fallback"] is True
        # Fallback seeds schema-shaped defaults for numeric fields.
        assert out["anomaly_severity"] == 0.5

    @pytest.mark.asyncio
    async def test_chat_with_tools_no_key(self):
        from app.services.kimi_api import KimiAPIClient

        client = KimiAPIClient(api_key="")
        result = await client.chat_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        )
        assert result.tool_calls == []
        assert result.content is None


# ─── Registry completeness ────────────────────────────────────────────────────

class TestRegistryContract:
    def test_all_agents_in_registry(self):
        expected = {
            "ingestion", "validation", "calculation", "reporting",
            "vvb_liaison", "quality_control", "client_success",
        }
        assert expected == set(AGENT_REGISTRY.keys())

    def test_agent_result_new_fields_serialize(self):
        result = AgentResult(
            status="completed",
            confidence_score=0.9,
            output_data={"x": 1},
            reasoning="because evidence",
            evidence={"k": "v"},
        )
        d = result.to_dict()
        assert d["reasoning"] == "because evidence"
        assert d["evidence"] == {"k": "v"}
        # Defaults stay backward-compatible.
        bare = AgentResult(status="completed", confidence_score=0.9, output_data={})
        assert bare.reasoning is None
        assert bare.evidence == {}
