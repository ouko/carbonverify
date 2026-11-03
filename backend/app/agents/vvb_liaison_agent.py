"""VVBLiaisonAgent: tracks registry submissions and drafts VVB responses."""

from datetime import UTC
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.core.logging import get_logger
from app.models import CalculationRun, Project, Report, ReportStatusEnum
from app.vvb_liaison.auto_responder import draft_clarification_response
from app.vvb_liaison.polling import RegistryPoller

logger = get_logger(__name__)

FINAL_STATUSES = ("approved", "verified", "vvb_approved", "rejected")
SUBMITTED_STATUSES = (ReportStatusEnum.submitted,)


class VVBLiaisonAgent(BaseAgent):
    """Agent that handles registry submission tracking and VVB communication.

    Uses the real registry-poller follow-up logic and the auto-responder
    knowledge base (escalating to the Kimi draft helper for unclassifiable
    queries) instead of simulated submissions.
    """

    agent_type = "vvb_liaison"

    async def run(self, context: dict[str, Any]) -> AgentResult:
        """Check submission status and draft responses to VVB queries."""
        project_id = self.project_id
        report_id = context.get("report_id")

        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return AgentResult(
                status="failed",
                confidence_score=0.0,
                output_data={},
                errors=["Project not found"],
                reasoning="VVB liaison aborted: project record not found.",
                evidence={},
            )

        # Get the report: explicit id, else latest submitted, else latest approved.
        report: Report | None = None
        if report_id:
            report_result = await self.db.execute(select(Report).where(Report.id == report_id))
            report = report_result.scalar_one_or_none()
        else:
            for statuses in (SUBMITTED_STATUSES, (ReportStatusEnum.approved,)):
                report_result = await self.db.execute(
                    select(Report)
                    .where(Report.project_id == project_id, Report.status.in_(statuses))
                    .order_by(Report.created_at.desc())
                    .limit(1)
                )
                report = report_result.scalar_one_or_none()
                if report:
                    break

        if not report:
            return self._no_data_result(
                reasoning=(
                    "No approved or submitted report exists for this project, so there "
                    "is nothing to track with the registry or VVB yet. Confidence set to "
                    "0.6 pending report approval."
                ),
                evidence={"project_id": str(project_id)},
            )

        registry = self._determine_registry(project.methodology.value)
        report_status = report.status.value if hasattr(report.status, "value") else str(report.status)

        # 1. Submission status freshness via the real follow-up logic.
        poller = RegistryPoller()
        follow_up = {"action": "none", "reason": "Report not yet submitted", "days_pending": 0}
        if report_status == "submitted":
            submitted_at = report.created_at
            if submitted_at is not None:
                if submitted_at.tzinfo is None:
                    submitted_at = submitted_at.replace(tzinfo=UTC)
                follow_up = poller.check_follow_up_needed(
                    submission_date=submitted_at,
                    current_status=report_status,
                )

        freshness = self._status_freshness(report_status, follow_up)

        # 2. Draft responses to any outstanding VVB queries.
        queries = self._extract_queries(report.vvb_feedback)
        calc_data = await self._calculation_context(report)
        responses: list[dict[str, Any]] = []
        answered = 0
        for query in queries:
            drafted = draft_clarification_response(
                query_text=query,
                project_data={
                    "name": project.name,
                    "methodology": project.methodology.value,
                },
                calculation_data=calc_data,
                methodology=project.methodology.value,
            )
            response_text = drafted["response_text"]
            source = "knowledge_base"
            if drafted.get("category") == "unknown":
                # Escalate unclassifiable queries to the Kimi drafting helper,
                # enriching the draft with methodology knowledge-base passages
                # when available (Phase 5; silently skipped on any failure).
                kb_passages = await self._knowledge_passages(
                    query, registry=self._determine_registry(project.methodology.value)
                )
                methodology_kb = "\n\n".join(
                    f"[{item['document']['methodology_id']}] {item['chunk']['content'][:800]}"
                    for item in kb_passages
                ) or None
                response_text = await self.kimi.draft_vvb_response(
                    query_text=query,
                    project_data={
                        "name": project.name,
                        "methodology": project.methodology.value,
                        "status": report_status,
                        "emissions_reduction": calc_data.get("emissions_reduction_tco2e"),
                    },
                    methodology_kb=methodology_kb,
                )
                source = "kimi_draft"
            answered += 1
            responses.append({
                "query": query,
                "category": drafted.get("category"),
                "response_text": response_text[:1000],
                "source": source,
                "suggested_human_review": drafted.get("suggested_human_review", source == "kimi_draft"),
            })

        coverage = (answered / len(queries)) if queries else 1.0

        # 3. Report quality from stored quality gates.
        quality_gates = (report.draft_content or {}).get("quality_gates", {})
        report_quality = 1.0 if quality_gates.get("passed", False) else 0.7

        confidence = max(0.0, min(1.0, freshness * 0.50 + coverage * 0.30 + report_quality * 0.20))

        reasoning = (
            f"Registry liaison for {registry}: report status '{report_status}', "
            f"follow-up action '{follow_up.get('action')}' ({follow_up.get('reason')}). "
            f"Status freshness {freshness:.2f}; {answered}/{len(queries)} VVB quer(ies) "
            f"drafted (coverage {coverage:.0%}); report quality {report_quality:.2f}. "
            "Confidence = freshness*0.50 + response_coverage*0.30 + report_quality*0.20."
        )

        evidence = {
            "report_id": str(report.id),
            "registry": registry,
            "report_status": report_status,
            "follow_up_action": follow_up.get("action"),
            "follow_up_reason": follow_up.get("reason"),
            "days_pending": follow_up.get("days_pending"),
            "query_count": len(queries),
            "answered_count": answered,
            "report_quality": report_quality,
        }

        output = self.build_output(
            reasoning,
            evidence,
            report_id=str(report.id),
            registry=registry,
            status=report_status,
            follow_up_action=follow_up.get("action"),
            responses=responses,
        )

        status = "completed" if confidence >= 0.85 else "queued_for_review"
        if follow_up.get("action") == "escalate":
            status = "queued_for_review"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
            reasoning=reasoning,
            evidence=evidence,
        )

    async def _knowledge_passages(
        self, question: str, registry: str | None = None
    ) -> list[dict[str, Any]]:
        """Best-effort knowledge-base enrichment; never breaks the agent.

        Silently returns [] when the knowledge base is not importable, errors,
        or has no ingested documents.
        """
        if self.db is None:
            return []
        try:
            from app.knowledge.service import KnowledgeBaseService

            return await KnowledgeBaseService(self.db).search(question, registry=registry, k=3)
        except Exception as exc:  # noqa: BLE001 — enrichment must never break the agent
            logger.debug("knowledge_enrichment_unavailable", agent_type=self.agent_type, error=str(exc))
            return []

    def _determine_registry(self, methodology: str) -> str:
        if "TPDDTEC" in methodology or "AMS" in methodology:
            return "gold_standard"
        return "verra"

    @staticmethod
    def _status_freshness(report_status: str, follow_up: dict[str, Any]) -> float:
        """Map registry/VVB status to a freshness score in [0, 1]."""
        if report_status in FINAL_STATUSES:
            return 1.0
        if report_status != "submitted":
            # Approved but not yet submitted — nothing stale yet.
            return 0.9
        action = follow_up.get("action")
        return {"wait": 0.9, "follow_up": 0.7, "escalate": 0.5}.get(str(action), 0.8)

    @staticmethod
    def _extract_queries(vvb_feedback: dict[str, Any] | None) -> list[str]:
        """Pull outstanding VVB query strings out of the free-form feedback blob."""
        if not isinstance(vvb_feedback, dict):
            return []
        raw = vvb_feedback.get("queries") or vvb_feedback.get("query")
        if isinstance(raw, str):
            return [raw]
        if not isinstance(raw, list):
            return []
        queries = []
        for item in raw:
            if isinstance(item, str):
                queries.append(item)
            elif isinstance(item, dict):
                text = item.get("query_text") or item.get("query")
                if text and not item.get("response"):
                    queries.append(str(text))
        return queries

    async def _calculation_context(self, report: Report) -> dict[str, Any]:
        """Best-effort calculation figures for the auto-responder templates."""
        result = await self.db.execute(
            select(CalculationRun).where(CalculationRun.id == report.calculation_run_id)
        )
        calc = result.scalar_one_or_none()
        if calc is None:
            return {}
        return {
            "fNRB_value": calc.fNRB_value,
            "emissions_reduction_tco2e": calc.emissions_reduction_tCO2e,
            "uncertainty_95CI": calc.uncertainty_95CI,
            "leakage_assessment": calc.leakage_assessment or {},
        }
