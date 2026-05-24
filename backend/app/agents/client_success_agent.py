"""ClientSuccessAgent: onboarding, progress updates, retention, upsell."""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import select, func

from app.agents.base import AgentResult, BaseAgent
from app.models import (
    CalculationRun,
    HumanReviewQueue,
    Project,
    ProjectStatusEnum,
    Report,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class ClientSuccessAgent(BaseAgent):
    """Agent that manages client lifecycle communications and engagement."""

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
            )

        actions: List[Dict[str, Any]] = []

        # 1. Onboarding sequence check
        if project.status == ProjectStatusEnum.onboarding:
            onboarding_actions = await self._check_onboarding(project)
            actions.extend(onboarding_actions)

        # 2. Progress update generation
        progress_actions = await self._generate_progress_update(project)
        actions.extend(progress_actions)

        # 3. Retention intervention check
        retention_actions = await self._check_retention_risk(project)
        actions.extend(retention_actions)

        # 4. Upsell recommendations
        upsell_actions = await self._generate_upsell_recommendations(project)
        actions.extend(upsell_actions)

        # Calculate engagement confidence
        engagement_score = await self._calculate_engagement_score(project)
        churn_risk = 1.0 - engagement_score

        # Confidence based on engagement metrics and churn risk model
        confidence = engagement_score * 0.6 + (1.0 - churn_risk) * 0.4

        output = {
            "trigger": trigger,
            "project_status": project.status.value,
            "engagement_score": round(engagement_score, 3),
            "churn_risk": round(churn_risk, 3),
            "action_count": len(actions),
            "actions": actions,
        }

        return AgentResult(
            status="completed",
            confidence_score=confidence,
            output_data=output,
        )

    async def _check_onboarding(self, project: Project) -> List[Dict[str, Any]]:
        """Check if onboarding tasks are complete."""
        actions = []
        days_since_creation = (datetime.utcnow() - project.created_at).days

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
        elif days_since_creation > 7 and project.status == ProjectStatusEnum.onboarding:
            actions.append({
                "type": "onboarding_intervention",
                "priority": "high",
                "message": "Schedule onboarding call — project stalled in onboarding for >7 days",
            })

        return actions

    async def _generate_progress_update(self, project: Project) -> List[Dict[str, Any]]:
        """Generate progress update for the client."""
        actions = []

        # Count calculations and reports
        calc_result = await self.db.execute(
            select(func.count(CalculationRun.id)).where(CalculationRun.project_id == project.id)
        )
        calc_count = calc_result.scalar() or 0

        report_result = await self.db.execute(
            select(func.count(Report.id)).where(Report.project_id == project.id)
        )
        report_count = report_result.scalar() or 0

        queue_result = await self.db.execute(
            select(func.count(HumanReviewQueue.id)).where(
                HumanReviewQueue.item_id == project.id,
                HumanReviewQueue.status == "pending",
            )
        )
        pending_reviews = queue_result.scalar() or 0

        actions.append({
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
        })

        return actions

    async def _check_retention_risk(self, project: Project) -> List[Dict[str, Any]]:
        """Identify retention risks and propose interventions."""
        actions = []

        # Check for stalled projects
        days_in_current_state = 30  # Placeholder
        result = await self.db.execute(
            select(CalculationRun).where(CalculationRun.project_id == project.id).order_by(CalculationRun.created_at.desc()).limit(1)
        )
        latest_calc = result.scalar_one_or_none()
        if latest_calc:
            days_in_current_state = (datetime.utcnow() - latest_calc.created_at).days

        if days_in_current_state > 14:
            actions.append({
                "type": "retention_intervention",
                "priority": "high",
                "message": f"No activity for {days_in_current_state} days. Send re-engagement email.",
            })

        # Check for repeated rejections
        rejections = await self.db.execute(
            select(func.count(CalculationRun.id)).where(
                CalculationRun.project_id == project.id,
                CalculationRun.status == "rejected",
            )
        )
        rejection_count = rejections.scalar() or 0
        if rejection_count >= 2:
            actions.append({
                "type": "retention_intervention",
                "priority": "critical",
                "message": f"{rejection_count} calculation rejections. Offer expert consultation.",
            })

        return actions

    async def _generate_upsell_recommendations(self, project: Project) -> List[Dict[str, Any]]:
        """Generate upsell recommendations based on project maturity."""
        actions = []

        if project.status == ProjectStatusEnum.verified:
            actions.append({
                "type": "upsell",
                "priority": "medium",
                "message": "Project verified. Recommend monitoring period extension or additional methodology.",
            })

        return actions

    async def _calculate_engagement_score(self, project: Project) -> float:
        """Calculate engagement score 0-1 based on activity metrics."""
        calc_result = await self.db.execute(
            select(func.count(CalculationRun.id)).where(CalculationRun.project_id == project.id)
        )
        calc_count = calc_result.scalar() or 0

        report_result = await self.db.execute(
            select(func.count(Report.id)).where(Report.project_id == project.id)
        )
        report_count = report_result.scalar() or 0

        # Simple scoring: more activity = higher engagement
        score = min(1.0, (calc_count * 0.15 + report_count * 0.2 + 0.3))
        return score
