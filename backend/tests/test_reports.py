"""Tests for report generation and VVB liaison system."""

from datetime import datetime, timezone, date

from app.reports.citations import get_citations_for_calculation, auto_cite_number, build_citation_index
from app.reports.cross_references import validate_report_cross_references
from app.reports.quality_gates import run_quality_gates
from app.reports.generator import get_template_name, build_report_context
from app.vvb_liaison.auto_responder import classify_query, draft_clarification_response
from app.vvb_liaison.polling import RegistryPoller


class TestCitationSystem:
    def test_get_citations_tpddtec(self):
        result = get_citations_for_calculation("TPDDTEC_v4")
        assert len(result) >= 4
        ids = [c["id"] for c in result]
        assert "C3" in ids  # Gold Standard TPDDTEC
        assert "C1" in ids  # IPCC

    def test_get_citations_vm0050(self):
        result = get_citations_for_calculation("VM0050")
        ids = [c["id"] for c in result]
        assert "C4" in ids  # VM0050
        assert "C5" in ids  # VCS Standard

    def test_auto_cite_number(self):
        result = auto_cite_number(1.58, "emission_factor", "TPDDTEC_v4")
        assert result["value"] == 1.58
        assert result["citation_id"] == "C1"
        assert "IPCC" in result["source"]

    def test_build_citation_index(self):
        calc_data = {
            "data_sources": [
                {"id": "abc-123", "source_type": "survey", "schema_version": "v1", "validation_status": "valid"},
            ]
        }
        result = build_citation_index(calc_data, "TPDDTEC_v4")
        assert len(result) > 0
        # Should include data source citation
        assert any("Data Source" in c["text"] for c in result)


class TestCrossReferenceValidator:
    def test_valid_report(self):
        html = """
        <p>See Table 1 for summary.</p>
        <table><tr><th>A</th></tr></table>
        <p class="caption">Table 1: Summary</p>
        <p>See Table 2 for details.</p>
        <table><tr><th>B</th></tr></table>
        <p class="caption">Table 2: Details</p>
        """
        result = validate_report_cross_references(html)
        assert result["valid"] is True
        assert result["summary"]["tables_found"] == 2

    def test_missing_citation(self):
        html = """
        <table><tr><th>A</th></tr></table>
        <p class="caption">Table 1: Summary</p>
        """
        result = validate_report_cross_references(html)
        assert result["valid"] is False
        assert any("not cited" in issue for issue in result["issues"])

    def test_orphan_citation(self):
        html = """
        <p>See Table 99 for summary.</p>
        """
        result = validate_report_cross_references(html)
        assert result["valid"] is False
        assert any("non-existent" in issue for issue in result["issues"])


class TestQualityGates:
    def test_tpddtec_completeness(self):
        html = """
        <h2>Executive Summary</h2>
        <p>Project achieved 1000.0 tCO2e with fNRB 0.30.</p>
        <h2>Project Description</h2>
        <h2>Monitoring Period</h2>
        <h2>Stove Distribution</h2>
        <h2>Kitchen Performance Test</h2>
        <h2>Thermal Efficiency</h2>
        <h2>Emissions Reduction</h2>
        <h2>Leakage</h2>
        <h2>Uncertainty</h2>
        """
        calc_data = {"emissions_reduction_tco2e": 1000, "fNRB_value": 0.30}
        result = run_quality_gates(html, calc_data, "TPDDTEC_v4")
        assert result["passed"] is True

    def test_missing_sections(self):
        html = "<h2>Executive Summary</h2>"
        calc_data = {"emissions_reduction_tco2e": 1000, "fNRB_value": 0.30}
        result = run_quality_gates(html, calc_data, "TPDDTEC_v4")
        assert result["passed"] is False
        assert any("Missing required sections" in issue for issue in result["issues"])

    def test_calculation_mismatch(self):
        html = "<h2>Executive Summary</h2><p>Emissions: 9999 tCO2e</p>"
        calc_data = {"emissions_reduction_tco2e": 1000, "fNRB_value": 0.30}
        result = run_quality_gates(html, calc_data, "TPDDTEC_v4")
        assert any("not found in report text" in issue for issue in result["issues"])


class TestReportGenerator:
    def test_get_template_name(self):
        assert get_template_name("TPDDTEC_v4") == "gs_tpddtec_v4.html"
        assert get_template_name("VM0050") == "verra_vm0050.html"
        assert get_template_name("UNKNOWN") == "gs_tpddtec_v4.html"

    def test_build_context(self):
        project = {"id": "test", "name": "Test Project", "methodology": "TPDDTEC_v4"}
        calc = {
            "id": "calc1",
            "fNRB_value": 0.30,
            "emissions_reduction_tCO2e": 5000,
            "uncertainty_95CI": 500,
            "monitoring_period_start": date(2024, 1, 1),
            "monitoring_period_end": date(2024, 12, 31),
            "monte_carlo": {
                "mean_reduction_tco2e": 5000,
                "uncertainty_95ci": {"lower": 4500, "upper": 5500},
                "conservative_estimate_tco2e": 4500,
            },
        }
        ds = [{"id": "ds1", "source_type": "survey", "schema_version": "v1", "validation_status": "valid"}]
        context = build_report_context(project, calc, ds, "TPDDTEC_v4")
        assert context["project"]["name"] == "Test Project"
        assert context["calc"]["fNRB_value"] == 0.30
        assert len(context["appendices"]) > 0
        assert len(context["citations"]) > 0


class TestVvbAutoResponder:
    def test_classify_fnrb_query(self):
        result = classify_query("What is the source of your fNRB value?")
        assert result == "fnrb_source"

    def test_classify_sample_size_query(self):
        result = classify_query("What was your KPT sample size?")
        assert result == "sample_size"

    def test_classify_unknown_query(self):
        result = classify_query("What is the meaning of life?")
        assert result is None

    def test_draft_response_fnrb(self):
        result = draft_clarification_response(
            "How was fNRB determined?",
            {"name": "Test Project"},
            {"fNRB_value": 0.30, "source_reference": "Spatial interpolation", "uncertainty_range": {"lower": 0.20, "upper": 0.40, "std_dev": 0.10}},
            "TPDDTEC_v4",
        )
        assert result["category"] == "fnrb_source"
        assert result["confidence"] >= 0.8
        assert "fNRB" in result["response_text"]
        assert result["suggested_human_review"] is False

    def test_draft_response_unknown(self):
        result = draft_clarification_response(
            "What is the philosophical basis for carbon markets?",
            {"name": "Test Project"},
            {},
            "TPDDTEC_v4",
        )
        assert result["category"] == "unknown"
        assert result["suggested_human_review"] is True


class TestRegistryPolling:
    def test_poller_initialization(self):
        poller = RegistryPoller()
        assert "verra" in poller.clients
        assert "gold_standard" in poller.clients
        assert "kenya_national" in poller.clients
        poller.close()

    def test_follow_up_needed_escalation(self):
        from datetime import timedelta
        poller = RegistryPoller()
        result = poller.check_follow_up_needed(
            submission_date=datetime.now(timezone.utc) - timedelta(days=35),
            current_status="under_review",
        )
        assert result["action"] == "escalate"
        assert result["urgency"] == "high"
        poller.close()

    def test_follow_up_needed_wait(self):
        from datetime import timedelta
        poller = RegistryPoller()
        result = poller.check_follow_up_needed(
            submission_date=datetime.now(timezone.utc) - timedelta(days=5),
            current_status="under_review",
        )
        assert result["action"] == "wait"
        poller.close()

    def test_no_follow_up_for_approved(self):
        from datetime import timedelta
        poller = RegistryPoller()
        result = poller.check_follow_up_needed(
            submission_date=datetime.now(timezone.utc) - timedelta(days=60),
            current_status="approved",
        )
        assert result["action"] == "none"
        poller.close()
