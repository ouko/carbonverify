"""VVBLiaisonAgent: submits to registries and tracks status."""

from typing import Any, Dict

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.models import Project, Report, ReportStatusEnum
from app.core.logging import get_logger

logger = get_logger(__name__)


class VVBLiaisonAgent(BaseAgent):
    """Agent that handles registry submission and VVB communication."""

    agent_type = "vvb_liaison"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Submit approved report to the appropriate registry."""
        project_id = self.project_id
        report_id = context.get("report_id")

        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return AgentResult(status="failed", confidence_score=0.0, output_data={}, errors=["Project not found"])

        # Get the report
        if report_id:
            report_result = await self.db.execute(select(Report).where(Report.id == report_id))
        else:
            report_result = await self.db.execute(
                select(Report)
                .where(Report.project_id == project_id, Report.status == ReportStatusEnum.approved)
                .order_by(Report.created_at.desc())
                .limit(1)
            )
        report = report_result.scalar_one_or_none()

        if not report:
            return AgentResult(
                status="failed",
                confidence_score=0.0,
                output_data={},
                errors=["No approved report found for submission"],
            )

        # Determine registry
        registry = self._determine_registry(project.methodology.value)

        # Simulate submission (actual API calls would go here)
        submission_result = await self._submit_to_registry(registry, report, project)

        # Update report status
        if submission_result.get("success"):
            report.status = ReportStatusEnum.submitted
            await self.db.commit()

        # Calculate confidence
        # 50% API response success
        # 30% historical acceptance rate for this registry
        # 20% report quality (methodology compliance)
        api_success = 1.0 if submission_result.get("success") else 0.0
        historical_rate = submission_result.get("historical_acceptance_rate", 0.85)
        report_quality = (report.draft_content.get("quality_gates", {}).get("passed", False) and 1.0 or 0.7)

        confidence = api_success * 0.50 + historical_rate * 0.30 + report_quality * 0.20

        output = {
            "report_id": str(report.id),
            "registry": registry,
            "submission_id": submission_result.get("submission_id"),
            "status": "submitted" if submission_result.get("success") else "failed",
            "tracking_url": submission_result.get("tracking_url"),
        }

        status = "completed" if submission_result.get("success") else "failed"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
        )

    def _determine_registry(self, methodology: str) -> str:
        if "TPDDTEC" in methodology or "AMS" in methodology:
            return "gold_standard"
        return "verra"

    async def _submit_to_registry(self, registry: str, report: Report, project) -> Dict[str, Any]:
        """Simulate registry submission."""
        logger.info("submitting_to_registry", registry=registry, report_id=str(report.id))

        # In production, this would call:
        # if registry == "verra":
        #     client = VerraClient(...)
        #     return await client.submit_monitoring_report(...)
        # else:
        #     client = GoldStandardClient(...)
        #     return await client.submit_verification_request(...)

        return {
            "success": True,
            "submission_id": f"SUB-{report.id.hex[:8].upper()}",
            "historical_acceptance_rate": 0.88,
            "tracking_url": f"https://{registry}.example.com/tracking/SUB-{report.id.hex[:8].upper()}",
        }
