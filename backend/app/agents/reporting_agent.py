"""ReportingAgent: generates monitoring reports and submission packages."""

from typing import Any

from sqlalchemy import select

from app.agents.base import BLEND_FORMULA, AgentResult, BaseAgent
from app.core.logging import get_logger
from app.models import (
    CalculationRun,
    DataSource,
    Project,
    Report,
    ReportStatusEnum,
    ReportTemplateTypeEnum,
)
from app.reports.generator import generate_report

logger = get_logger(__name__)

COMPLETENESS_SCHEMA = {
    "type": "object",
    "properties": {
        "completeness": {
            "type": "number",
            "description": "0-1 score: how completely does the draft cover the calculation results?",
        },
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["completeness"],
}


class ReportingAgent(BaseAgent):
    """Agent that generates audit-ready monitoring reports."""

    agent_type = "reporting"

    async def run(self, context: dict[str, Any]) -> AgentResult:
        """Generate report from calculation run and data sources."""
        project_id = self.project_id
        calc_run_id = context.get("calculation_run_id")

        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return AgentResult(
                status="failed",
                confidence_score=0.0,
                output_data={},
                errors=["Project not found"],
                reasoning="Report generation aborted: project record not found.",
                evidence={},
            )

        # Get latest calculation run if not specified
        if calc_run_id is None:
            calc_result = await self.db.execute(
                select(CalculationRun)
                .where(CalculationRun.project_id == project_id)
                .order_by(CalculationRun.created_at.desc())
                .limit(1)
            )
            calc_run = calc_result.scalar_one_or_none()
        else:
            calc_result = await self.db.execute(
                select(CalculationRun).where(CalculationRun.id == calc_run_id)
            )
            calc_run = calc_result.scalar_one_or_none()

        if not calc_run:
            return self._no_data_result(
                reasoning=(
                    "No calculation run exists for this project, so no monitoring "
                    "report can be generated yet. Confidence set to 0.6 pending calculation output."
                ),
                evidence={"calculation_run_id": str(calc_run_id) if calc_run_id else None},
            )

        # Get data sources
        ds_result = await self.db.execute(
            select(DataSource).where(DataSource.project_id == project_id)
        )
        data_sources = ds_result.scalars().all()

        # Build project dict for report generator
        project_dict = {
            "id": str(project.id),
            "name": project.name,
            "methodology": project.methodology.value,
            "processed_data": {},
        }

        # Build calculation run dict
        calc_dict = {
            "id": str(calc_run.id),
            "fNRB_value": calc_run.fNRB_value,
            "emissions_reduction_tCO2e": calc_run.emissions_reduction_tCO2e,
            "uncertainty_95CI": calc_run.uncertainty_95CI,
            "monitoring_period_start": calc_run.monitoring_period_start,
            "monitoring_period_end": calc_run.monitoring_period_end,
            "baseline_emissions": calc_run.leakage_assessment.get("baseline_emissions_tco2e", {}),
            "project_emissions": {},
            "monte_carlo": {
                "mean_reduction_tco2e": calc_run.emissions_reduction_tCO2e,
                "uncertainty_95ci": {"lower": (calc_run.emissions_reduction_tCO2e or 0) - (calc_run.uncertainty_95CI or 0) / 2, "upper": (calc_run.emissions_reduction_tCO2e or 0) + (calc_run.uncertainty_95CI or 0) / 2},
                "conservative_estimate_tco2e": (calc_run.emissions_reduction_tCO2e or 0) - (calc_run.uncertainty_95CI or 0) / 2,
            },
            "methodology_validation": {"compliance_score": calc_run.methodology_compliance_score or 0},
        }

        ds_list = [
            {
                "id": str(ds.id),
                "source_type": ds.source_type.value,
                "validation_status": ds.validation_status.value,
                "schema_version": ds.schema_version,
                "record_count": ds.processed_data.get("records_extracted", 0) if ds.processed_data else 0,
            }
            for ds in data_sources
        ]

        methodology = project.methodology.value

        # Generate report
        try:
            report_result = generate_report(
                project=project_dict,
                calculation_run=calc_dict,
                data_sources=ds_list,
                methodology=methodology,
            )
        except Exception as exc:
            logger.error("report_generation_failed", error=str(exc))
            return AgentResult(
                status="failed",
                confidence_score=0.0,
                output_data={},
                errors=[str(exc)],
                reasoning=f"Report generation failed: {exc}",
                evidence={"stage": "generate_report"},
            )

        # Run quality gates on the HTML
        quality = report_result.get("quality_gates", {})
        html = report_result.get("html", "")

        # Calculate heuristic confidence from gate pass rate:
        # 40% quality gates passed
        # 30% template compliance (methodology score)
        # 20% citation completeness
        # 10% grammar score
        gate_checks = [
            quality.get("passed", False),
            not quality.get("issues"),
            not quality.get("warnings"),
            quality.get("cross_reference_validation", {}).get("valid", True),
        ]
        gate_pass_rate = sum(1 for g in gate_checks if g) / len(gate_checks)
        template_compliance = (calc_run.methodology_compliance_score or 0) / 100.0

        heuristic = (
            gate_pass_rate * 0.55
            + template_compliance * 0.30
            + (1.0 if not quality.get("warnings") else 0.9) * 0.15
        )

        # LLM evaluation of draft completeness against the calculation results.
        llm_review = await self.reason_with_llm(
            task_prompt=(
                "Evaluate this monitoring report draft for completeness against the "
                "calculation results. Are all key figures (emissions reduction, fNRB, "
                "uncertainty, leakage, methodology compliance) present and consistent? "
                "Score completeness 0-1 and list gaps."
            ),
            context={
                "methodology": methodology,
                "calculation": {
                    "emissions_reduction_tCO2e": calc_run.emissions_reduction_tCO2e,
                    "fNRB_value": calc_run.fNRB_value,
                    "uncertainty_95CI": calc_run.uncertainty_95CI,
                    "methodology_compliance_score": calc_run.methodology_compliance_score,
                },
                "data_sources": ds_list,
                "quality_gates": quality,
                "draft_excerpt": html[:3000],
            },
            response_schema=COMPLETENESS_SCHEMA,
        )
        llm_completeness: float | None = None
        llm_gaps = []
        if not llm_review.get("_fallback"):
            raw = llm_review.get("completeness")
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                llm_completeness = max(0.0, min(1.0, float(raw)))
            gaps = llm_review.get("gaps")
            if isinstance(gaps, list):
                llm_gaps = [str(g) for g in gaps]

        confidence = self.blend_confidence(heuristic, llm_completeness)
        blend_note = (
            f"Blended heuristic ({heuristic:.2f}) with LLM completeness ({llm_completeness:.2f}) via {BLEND_FORMULA}."
            if llm_completeness is not None
            else f"LLM evaluation unavailable; heuristic score stands alone (blending {BLEND_FORMULA} not applied)."
        )

        # Create Report record
        template_type = (
            ReportTemplateTypeEnum.GoldStandard_TPDDTEC
            if "TPDDTEC" in methodology
            else ReportTemplateTypeEnum.Verra_VM0050
        )

        report = Report(
            project_id=project_id,
            calculation_run_id=calc_run.id,
            template_type=template_type,
            draft_content={
                "html": html[:5000],  # Truncate for storage
                "quality_gates": quality,
                "pdf_path": report_result.get("pdf_path"),
            },
            status=ReportStatusEnum.draft,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)

        issue_count = len(quality.get("issues", []))
        warning_count = len(quality.get("warnings", []))
        reasoning = (
            f"Generated {methodology} report from calculation run {calc_run.id}: "
            f"quality gates passed={quality.get('passed')} "
            f"({gate_pass_rate:.0%} gate checks pass, {issue_count} issue(s), {warning_count} warning(s)); "
            f"methodology compliance {calc_run.methodology_compliance_score or 0:.0f}%; "
            f"cross-reference validation "
            f"{'passed' if quality.get('cross_reference_validation', {}).get('valid', True) else 'failed'}. "
            f"{blend_note}"
            + (f" LLM-noted gaps: {'; '.join(llm_gaps[:5])}." if llm_gaps else "")
        )

        evidence = {
            "report_id": str(report.id),
            "calculation_run_id": str(calc_run.id),
            "gate_pass_rate": round(gate_pass_rate, 3),
            "quality_gates_passed": bool(quality.get("passed")),
            "issue_count": issue_count,
            "warning_count": warning_count,
            "template_compliance": round(template_compliance, 3),
            "llm_completeness": llm_completeness,
            "llm_gaps": llm_gaps,
        }

        output = self.build_output(
            reasoning,
            evidence,
            report_id=str(report.id),
            calculation_run_id=str(calc_run.id),
            pdf_path=report_result.get("pdf_path"),
            quality_gates=quality,
            status=report_result.get("status"),
            heuristic_confidence=round(heuristic, 3),
            llm_completeness=llm_completeness,
        )

        status = "completed" if confidence >= 0.85 else "queued_for_review"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
            reasoning=reasoning,
            evidence=evidence,
        )
