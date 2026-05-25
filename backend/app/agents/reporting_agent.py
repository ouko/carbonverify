"""ReportingAgent: generates monitoring reports and submission packages."""

from typing import Any, Dict

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.models import CalculationRun, DataSource, Project, Report, ReportTemplateTypeEnum, ReportStatusEnum
from app.reports.generator import generate_report
from app.core.logging import get_logger

logger = get_logger(__name__)


class ReportingAgent(BaseAgent):
    """Agent that generates audit-ready monitoring reports."""

    agent_type = "reporting"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Generate report from calculation run and data sources."""
        project_id = self.project_id
        calc_run_id = context.get("calculation_run_id")

        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return AgentResult(status="failed", confidence_score=0.0, output_data={}, errors=["Project not found"])

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
            return AgentResult(
                status="failed",
                confidence_score=0.0,
                output_data={},
                errors=["No calculation run found for reporting"],
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
            )

        # Run quality gates on the HTML
        quality = report_result.get("quality_gates", {})
        html = report_result.get("html", "")

        # Calculate confidence
        # 40% quality gates passed
        # 30% template compliance (methodology score)
        # 20% citation completeness
        # 10% grammar score
        quality_passed = 1.0 if quality.get("passed") else 0.5
        template_compliance = (calc_run.methodology_compliance_score or 0) / 100.0
        citation_completeness = 1.0 if not quality.get("issues") else 0.8
        grammar_score = 1.0 if not quality.get("warnings") else 0.9

        confidence = (
            quality_passed * 0.40
            + template_compliance * 0.30
            + citation_completeness * 0.20
            + grammar_score * 0.10
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

        output = {
            "report_id": str(report.id),
            "calculation_run_id": str(calc_run.id),
            "pdf_path": report_result.get("pdf_path"),
            "quality_gates": quality,
            "status": report_result.get("status"),
        }

        status = "completed" if confidence >= 0.85 else "queued_for_review"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
        )
