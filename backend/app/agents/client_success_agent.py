"""ClientSuccessAgent: onboarding, progress updates, retention, upsell."""

from datetime import date, datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import func, select

from app.agents.base import AgentResult, BaseAgent
from app.models import (
    AgentRun,
    CalculationRun,
    Developer,
    FileUpload,
    HumanReviewQueue,
    Project,
    ProjectStatusEnum,
    Report,
    SupportTicket,
    SurveyResponse,
    WhatsAppConversation,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

CLIENT_MESSAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string", "description": "Short professional client update message (max ~150 words)"},
    },
    "required": ["subject", "body"],
}

# Monitoring period end within this many days triggers an upsell/expiry nudge.
MONITORING_PERIOD_APPROACHING_DAYS = 90


class ClientSuccessAgent(BaseAgent):
    """Agent that manages client lifecycle communications and engagement.

    Computes a churn-risk score from owner presence, recency of activity,
    open support tickets, and survey response rates, then drafts a client
    update message via the LLM (with graceful fallback).
    """

    agent_type = "client_success"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Generate client success actions based on project state."""
        project_id = self.project_id
        trigger = context.get("trigger", "milestone")  # milestone | schedule | usage_pattern

        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return AgentResult(
                status="failed",
                confidence_score=0.0,
                output_data={},
                errors=["Project not found"],
                reasoning="Client success check aborted: project record not found.",
                evidence={},
            )

        # 1. Owner account health.
        owner = await self._get_owner(project)

        # 2. Recency of activity (days since last agent run / calc / upload).
        days_since_activity = await self._days_since_activity(project)

        # 3. Support burden.
        open_tickets = await self._count_open_tickets(project)

        # 4. Survey engagement.
        survey_stats = await self._survey_stats(project)

        # 5. Churn-risk score (0 = healthy, 1 = likely churn).
        churn_risk = self._compute_churn_risk(
            project=project,
            owner_present=owner is not None,
            days_since_activity=days_since_activity,
            open_tickets=open_tickets,
            survey_stats=survey_stats,
        )
        engagement_score = 1.0 - churn_risk

        actions: List[Dict[str, Any]] = []
        actions.extend(await self._check_onboarding(project))
        actions.extend(await self._generate_progress_update(project))
        actions.extend(self._check_retention_risk(project, days_since_activity, churn_risk))
        actions.extend(self._generate_upsell_recommendations(project))

        # 6. LLM-drafted client update message (fallback to template).
        message_context = {
            "project_name": project.name,
            "project_status": project.status.value,
            "methodology": project.methodology.value,
            "days_since_activity": days_since_activity,
            "open_tickets": open_tickets,
            "survey_response_rate": survey_stats["response_rate"],
            "pending_reviews": await self._count_pending_reviews(project),
            "crediting_period_end": str(project.crediting_period_end),
        }
        llm_message = await self.reason_with_llm(
            task_prompt=(
                "Draft a short, professional client update message for this carbon "
                "credit project. Summarize current status, recent activity, any "
                "requested actions, and next steps. Be honest about delays."
            ),
            context=message_context,
            response_schema=CLIENT_MESSAGE_SCHEMA,
        )
        if not llm_message.get("_fallback") and llm_message.get("body"):
            client_message = {
                "subject": llm_message.get("subject", f"{project.name} — status update"),
                "body": llm_message.get("body"),
                "source": "llm_draft",
            }
        else:
            client_message = {
                "subject": f"{project.name} — status update",
                "body": (
                    f"Hello — here is the latest update on {project.name} "
                    f"(status: {project.status.value}). "
                    f"Days since last recorded activity: {days_since_activity}. "
                    f"Open support tickets: {open_tickets}. "
                    + ("Next step: please review the pending items in your dashboard."
                       if open_tickets or days_since_activity > 14 else
                       "Your project is progressing as expected — no action needed.")
                ),
                "source": "template_fallback",
            }

        confidence = engagement_score * 0.6 + (1.0 - churn_risk) * 0.4

        reasoning = (
            f"Client success check for '{project.name}' (status {project.status.value}): "
            f"owner account {'present' if owner else 'missing'}, "
            f"{days_since_activity} day(s) since last activity, "
            f"{open_tickets} open support ticket(s), "
            f"survey response rate {survey_stats['response_rate']:.0%} "
            f"({survey_stats['responses']}/{survey_stats['conversations']} conversations), "
            f"churn risk {churn_risk:.2f}. Generated {len(actions)} action(s) and a "
            f"client update message ({client_message['source']})."
        )

        evidence = {
            "project_status": project.status.value,
            "owner_present": owner is not None,
            "owner_company": owner.company_name if owner else None,
            "days_since_activity": days_since_activity,
            "open_tickets": open_tickets,
            "survey_responses": survey_stats["responses"],
            "survey_conversations": survey_stats["conversations"],
            "survey_response_rate": round(survey_stats["response_rate"], 3),
            "churn_risk": round(churn_risk, 3),
            "engagement_score": round(engagement_score, 3),
            "crediting_period_end": str(project.crediting_period_end),
            "monitoring_period_approaching": self._monitoring_period_approaching(project),
        }

        output = self.build_output(
            reasoning,
            evidence,
            trigger=trigger,
            project_status=project.status.value,
            engagement_score=round(engagement_score, 3),
            churn_risk=round(churn_risk, 3),
            action_count=len(actions),
            actions=actions,
            client_update_message=client_message,
        )

        return AgentResult(
            status="completed",
            confidence_score=max(0.0, min(1.0, confidence)),
            output_data=output,
            reasoning=reasoning,
            evidence=evidence,
        )

    # ─── Data helpers ─────────────────────────────────────────────────────

    async def _get_owner(self, project: Project) -> Developer | None:
        """Fetch the developer (account owner) record for the project."""
        result = await self.db.execute(
            select(Developer).where(Developer.id == project.developer_id)
        )
        return result.scalar_one_or_none()

    async def _days_since_activity(self, project: Project) -> int:
        """Days since the most recent of: agent run, calculation, or upload."""
        now = datetime.now(timezone.utc)
        latest: datetime | None = None
        for model in (AgentRun, CalculationRun, FileUpload):
            result = await self.db.execute(
                select(model.created_at)
                .where(model.project_id == project.id)
                .order_by(model.created_at.desc())
                .limit(1)
            )
            created_at = result.scalar()
            if created_at is not None and (latest is None or created_at > latest):
                latest = created_at
        if latest is None:
            # Fall back to project creation.
            latest = project.created_at
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        return max(0, (now - latest).days)

    async def _count_open_tickets(self, project: Project) -> int:
        result = await self.db.execute(
            select(func.count(SupportTicket.id)).where(
                SupportTicket.project_id == project.id,
                SupportTicket.status == "open",
            )
        )
        return result.scalar() or 0

    async def _count_pending_reviews(self, project: Project) -> int:
        result = await self.db.execute(
            select(func.count(HumanReviewQueue.id)).where(
                HumanReviewQueue.item_id == project.id,
                HumanReviewQueue.status == "pending",
            )
        )
        return result.scalar() or 0

    async def _survey_stats(self, project: Project) -> Dict[str, Any]:
        """Survey response rate: responses over completed conversations."""
        conv_result = await self.db.execute(
            select(func.count(WhatsAppConversation.id)).where(
                WhatsAppConversation.project_id == project.id,
            )
        )
        conversations = conv_result.scalar() or 0
        resp_result = await self.db.execute(
            select(func.count(SurveyResponse.id)).where(
                SurveyResponse.project_id == project.id,
            )
        )
        responses = resp_result.scalar() or 0
        return {
            "conversations": conversations,
            "responses": responses,
            "response_rate": (responses / conversations) if conversations else 0.0,
        }

    # ─── Scoring & actions ────────────────────────────────────────────────

    @staticmethod
    def _compute_churn_risk(
        project: Project,
        owner_present: bool,
        days_since_activity: int,
        open_tickets: int,
        survey_stats: Dict[str, Any],
    ) -> float:
        """Weighted churn-risk score in [0, 1]."""
        risk = 0.1
        if not owner_present:
            risk += 0.25
        if days_since_activity > 30:
            risk += 0.35
        elif days_since_activity > 14:
            risk += 0.2
        risk += min(0.2, open_tickets * 0.1)
        risk += 0.1 * (1.0 - survey_stats["response_rate"])
        if project.status == ProjectStatusEnum.rejected:
            risk += 0.3
        return max(0.0, min(1.0, risk))

    @staticmethod
    def _monitoring_period_approaching(project: Project) -> bool:
        end = project.crediting_period_end
        if end is None:
            return False
        today = date.today()
        if end < today:
            return True
        return (end - today).days <= MONITORING_PERIOD_APPROACHING_DAYS

    async def _check_onboarding(self, project: Project) -> List[Dict[str, Any]]:
        """Check if onboarding tasks are complete."""
        actions: List[Dict[str, Any]] = []
        if project.status != ProjectStatusEnum.onboarding:
            return actions

        created_at = project.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        days_since_creation = (datetime.now(timezone.utc) - created_at).days if created_at else 0

        if days_since_creation <= 1:
            actions.append({
                "type": "onboarding_welcome",
                "priority": "high",
                "message": "Send welcome email with project setup guide",
            })
        elif days_since_creation <= 3:
            actions.append({
                "type": "onboarding_reminder",
                "priority": "medium",
                "message": "Remind to upload baseline data and methodology documents",
            })
        elif days_since_creation > 7:
            actions.append({
                "type": "onboarding_intervention",
                "priority": "high",
                "message": "Schedule onboarding call — project stalled in onboarding for >7 days",
            })

        return actions

    async def _generate_progress_update(self, project: Project) -> List[Dict[str, Any]]:
        """Generate progress update for the client."""
        calc_result = await self.db.execute(
            select(func.count(CalculationRun.id)).where(CalculationRun.project_id == project.id)
        )
        calc_count = calc_result.scalar() or 0

        report_result = await self.db.execute(
            select(func.count(Report.id)).where(Report.project_id == project.id)
        )
        report_count = report_result.scalar() or 0

        pending_reviews = await self._count_pending_reviews(project)

        return [{
            "type": "progress_update",
            "priority": "low",
            "message": (
                f"Project status: {project.status.value}. "
                f"Calculations: {calc_count}. Reports: {report_count}. "
                f"Pending reviews: {pending_reviews}."
            ),
            "metrics": {
                "calculations": calc_count,
                "reports": report_count,
                "pending_reviews": pending_reviews,
            },
        }]

    def _check_retention_risk(
        self,
        project: Project,
        days_since_activity: int,
        churn_risk: float,
    ) -> List[Dict[str, Any]]:
        """Identify retention risks and propose interventions."""
        actions = []

        if days_since_activity > 14:
            actions.append({
                "type": "retention_intervention",
                "priority": "high",
                "message": f"No activity for {days_since_activity} days. Send re-engagement email.",
            })

        if churn_risk >= 0.6:
            actions.append({
                "type": "retention_intervention",
                "priority": "critical",
                "message": f"Churn risk {churn_risk:.2f} exceeds 0.6 threshold. Offer expert consultation.",
            })

        return actions

    def _generate_upsell_recommendations(self, project: Project) -> List[Dict[str, Any]]:
        """Generate upsell recommendations based on project maturity."""
        actions = []

        if project.status == ProjectStatusEnum.verified:
            actions.append({
                "type": "upsell",
                "priority": "medium",
                "message": "Project verified. Recommend monitoring period extension or additional methodology.",
            })

        if self._monitoring_period_approaching(project):
            actions.append({
                "type": "upsell",
                "priority": "medium",
                "message": (
                    f"Monitoring period ends {project.crediting_period_end} "
                    "(within 90 days). Propose renewal or expansion to adjacent regions."
                ),
            })

        return actions
