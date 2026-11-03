"""Kimi Claw Orchestrator: master controller for multi-agent project lifecycle."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AGENT_REGISTRY, AgentResult
from app.core.logging import get_logger
from app.models import (
    AgentRun,
    AgentStatusEnum,
    AgentTypeEnum,
    HumanReviewQueue,
    Project,
    ProjectStatusEnum,
    QueueItemTypeEnum,
    QueueStatusEnum,
)
from app.orchestrator.audit_chain import record_decision
from app.orchestrator.events import EventLogger
from app.orchestrator.pubsub import agent_pubsub

logger = get_logger(__name__)

# ─── State Machine Definition ─────────────────────────────────────────────────

STATE_TRANSITIONS = {
    ProjectStatusEnum.onboarding: {
        "data_collection": [AgentTypeEnum.ingestion, AgentTypeEnum.client_success],
    },
    ProjectStatusEnum.data_collection: {
        "calculation": [AgentTypeEnum.validation, AgentTypeEnum.ingestion],
    },
    ProjectStatusEnum.calculation: {
        "review": [AgentTypeEnum.calculation, AgentTypeEnum.quality_control],
    },
    ProjectStatusEnum.review: {
        "submitted": [AgentTypeEnum.reporting],
    },
    ProjectStatusEnum.submitted: {
        "verified": [AgentTypeEnum.vvb_liaison],
    },
    ProjectStatusEnum.verified: {
        "monitoring": [AgentTypeEnum.client_success, AgentTypeEnum.quality_control],
    },
    ProjectStatusEnum.monitoring: {
        "data_collection": [AgentTypeEnum.ingestion, AgentTypeEnum.client_success],
    },
}

# Trigger → next state mapping
TRIGGER_STATES = {
    "data_complete": ProjectStatusEnum.data_collection,
    "validation_passed": ProjectStatusEnum.calculation,
    "calculation_complete": ProjectStatusEnum.review,
    "report_approved": ProjectStatusEnum.submitted,
    "registry_approved": ProjectStatusEnum.verified,
    "monitoring_period_complete": ProjectStatusEnum.monitoring,
}

# States the lifecycle driver actively pushes through (onboarding → submitted).
# verified/monitoring are steady-state (external actors: registry, VVB), rejected is terminal.
LIFECYCLE_DRIVE_STATES = (
    ProjectStatusEnum.onboarding,
    ProjectStatusEnum.data_collection,
    ProjectStatusEnum.calculation,
    ProjectStatusEnum.review,
    ProjectStatusEnum.submitted,
)

# States where autonomous advancement must not operate.
STEADY_STATES = (
    ProjectStatusEnum.verified,
    ProjectStatusEnum.monitoring,
    ProjectStatusEnum.rejected,
)


def trigger_for_next_state(next_state: str) -> Optional[str]:
    """Reverse-map a next-state name to its lifecycle trigger."""
    for trigger, state in TRIGGER_STATES.items():
        if state.value == next_state:
            return trigger
    return None


class KimiClawOrchestrator:
    """Master orchestrator that dispatches agents and manages project lifecycle."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.event_logger = EventLogger(db)

    async def process_project(self, project_id: uuid.UUID, trigger: str, context: Optional[Dict[str, Any]] = None):
        """Main entry point: process a project state transition."""
        context = context or {}

        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            logger.error("orchestrator_project_not_found", project_id=str(project_id))
            return {"error": "Project not found"}

        current_state = project.status
        logger.info(
            "orchestrator_process_start",
            project_id=str(project_id),
            current_state=current_state.value,
            trigger=trigger,
        )

        # Determine target state from trigger
        target_state = TRIGGER_STATES.get(trigger)
        if target_state is None:
            logger.warning("orchestrator_unknown_trigger", trigger=trigger)
            target_state = current_state

        # Log state transition
        await self.event_logger.log_state_transition(
            project_id=project_id,
            from_state=current_state.value,
            to_state=target_state.value,
            details={"trigger": trigger},
        )

        # Update project state
        if target_state != current_state:
            project.status = target_state
            await self.db.commit()
            await self._publish_project_update(project_id, {
                "type": "state_transition",
                "from_state": current_state.value,
                "to_state": target_state.value,
                "trigger": trigger,
            })

        # Dispatch agents for the new state
        agents_to_run = STATE_TRANSITIONS.get(target_state, {})
        # Find which agent keys map to the next logical state
        next_state_key = None
        for key, agents in agents_to_run.items():
            # key is the next state name (as string)
            next_state_key = key
            break

        if next_state_key:
            agent_types = agents_to_run.get(next_state_key, [])
        else:
            agent_types = []

        results = []
        for agent_type in agent_types:
            result = await self.dispatch_agent(project_id, agent_type.value, trigger, context)
            results.append(result)

        return {
            "project_id": str(project_id),
            "state": target_state.value,
            "trigger": trigger,
            "agent_results": [r.to_dict() for r in results],
        }

    async def advance_project(
        self,
        project_id: uuid.UUID,
        max_steps: int = 3,
        _visited: Optional[set] = None,
    ) -> Dict[str, Any]:
        """Autonomously advance a project through lifecycle states.

        Runs the current state's required agents via :meth:`dispatch_agent`.
        If ALL results are >= 0.95 confidence, commits the transition to the
        next state and recurses (up to ``max_steps``). Stops on any
        human-review/escalation result, a steady/terminal state, a revisited
        state (loop guard), or step exhaustion.

        Returns a nested result dict; ``advanced`` is True on each committed
        transition, with the recursion result under ``next``.
        """
        _visited = _visited or set()

        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            logger.error("orchestrator_project_not_found", project_id=str(project_id))
            return {"error": "Project not found"}

        state = project.status
        base = {"project_id": str(project_id), "state": state.value}

        if state in STEADY_STATES:
            return {**base, "advanced": False, "reason": "steady_state"}
        if state in _visited:
            logger.warning("orchestrator_advance_loop_guard", project_id=str(project_id), state=state.value)
            return {**base, "advanced": False, "reason": "loop_guard"}
        if max_steps <= 0:
            return {**base, "advanced": False, "reason": "max_steps"}

        transitions = STATE_TRANSITIONS.get(state, {})
        if not transitions:
            return {**base, "advanced": False, "reason": "no_transition_defined"}
        next_state_key, agent_types = next(iter(transitions.items()))
        trigger = trigger_for_next_state(next_state_key)
        if trigger is None:
            return {**base, "advanced": False, "reason": "no_trigger_defined"}

        _visited = _visited | {state}
        logger.info(
            "orchestrator_advance_start",
            project_id=str(project_id),
            state=state.value,
            next_state=next_state_key,
            trigger=trigger,
        )

        agent_results = []
        for agent_type in agent_types:
            agent_result = await self.dispatch_agent(project_id, agent_type.value, trigger, {})
            agent_results.append(agent_result)

        if all(r.status != "failed" and r.confidence_score >= 0.95 for r in agent_results):
            await self.event_logger.log_state_transition(
                project_id=project_id,
                from_state=state.value,
                to_state=next_state_key,
                details={"trigger": trigger, "source": "auto_advance"},
            )
            project.status = ProjectStatusEnum(next_state_key)
            await self.db.commit()
            await self._publish_project_update(project_id, {
                "type": "state_transition",
                "from_state": state.value,
                "to_state": next_state_key,
                "trigger": trigger,
            })

            next_result = await self.advance_project(project_id, max_steps - 1, _visited)
            return {
                **base,
                "advanced": True,
                "to_state": next_state_key,
                "trigger": trigger,
                "agent_results": [r.to_dict() for r in agent_results],
                "next": next_result,
            }

        # Any agent below the auto-advance threshold has already queued a
        # human review item (or escalation) inside dispatch_agent.
        return {
            **base,
            "advanced": False,
            "reason": "insufficient_confidence",
            "agent_results": [r.to_dict() for r in agent_results],
        }

    async def dispatch_agent(
        self,
        project_id: uuid.UUID,
        agent_type: str,
        trigger_event: str,
        context: Dict[str, Any],
    ) -> AgentResult:
        """Dispatch a single agent and handle its result."""

        # Validate agent type first
        agent_cls = AGENT_REGISTRY.get(agent_type)
        if not agent_cls:
            error_msg = f"Unknown agent type: {agent_type}"
            logger.error("orchestrator_unknown_agent", agent_type=agent_type)
            return AgentResult(status="failed", confidence_score=0.0, output_data={}, errors=[error_msg])

        # Create AgentRun record
        agent_run = AgentRun(
            project_id=project_id,
            agent_type=AgentTypeEnum(agent_type),
            status=AgentStatusEnum.running,
            trigger_event=trigger_event,
            input_data={"context": context, "trigger": trigger_event},
        )
        self.db.add(agent_run)
        await self.db.commit()
        await self.db.refresh(agent_run)

        await self.event_logger.log_agent_dispatch(
            project_id=project_id,
            agent_type=agent_type,
            trigger_event=trigger_event,
        )

        await self._publish_project_update(project_id, {
            "type": "agent_dispatch",
            "agent_type": agent_type,
            "agent_run_id": str(agent_run.id),
        })

        # Instantiate and run agent
        agent = agent_cls(project_id=project_id, db_session=self.db)
        result = await agent.execute(trigger_event=trigger_event, context=context)

        # Update AgentRun with results
        agent_run.status = AgentStatusEnum(result.status)
        agent_run.output_data = result.output_data
        agent_run.confidence_score = result.confidence_score
        agent_run.execution_time_ms = result.execution_time_ms
        agent_run.error_message = result.errors[0] if result.errors else None
        agent_run.completed_at = datetime.now(timezone.utc)
        await self.db.commit()

        await self.event_logger.log_agent_complete(
            project_id=project_id,
            agent_run_id=agent_run.id,
            confidence_score=result.confidence_score,
            details={"agent_type": agent_type, "status": result.status},
        )

        await self._publish_project_update(project_id, {
            "type": "agent_complete",
            "agent_type": agent_type,
            "agent_run_id": str(agent_run.id),
            "status": result.status,
            "confidence": result.confidence_score,
        })

        # Handle confidence-based routing
        await self._handle_confidence_result(project_id, agent_type, agent_run.id, result, context)

        return result

    async def _handle_confidence_result(
        self,
        project_id: uuid.UUID,
        agent_type: str,
        agent_run_id: uuid.UUID,
        result: AgentResult,
        context: Dict[str, Any],
    ):
        """Route based on confidence score: auto-advance, human review, or escalate."""
        score = result.confidence_score
        tier = "auto_advance" if score >= 0.95 else ("human_review" if score >= 0.85 else "escalate")

        await self.event_logger.log_confidence_check(
            project_id=project_id,
            agent_type=agent_type,
            confidence_score=score,
            decision=tier,
        )

        if tier == "auto_advance":
            logger.info("orchestrator_auto_advance", project_id=str(project_id), agent_type=agent_type)
            # Trigger next state automatically
            next_trigger = self._get_next_trigger(agent_type)
            await self.event_logger.log_auto_advance(
                project_id=project_id,
                from_state="",
                to_state=next_trigger or "",
                agent_type=agent_type,
            )
            await record_decision(
                self.db,
                project_id=project_id,
                agent_type=agent_type,
                action="auto_advance",
                confidence_score=score,
                reasoning=self._decision_reasoning(
                    agent_type, agent_run_id, result, tier, next_trigger=next_trigger
                ),
                input_summary={
                    "agent_run_id": str(agent_run_id),
                    "output_keys": sorted(result.output_data.keys()) if isinstance(result.output_data, dict) else [],
                    "errors": result.errors,
                },
                actor=f"agent:{agent_type}",
            )
            # Don't recursively call to avoid loops — just log the recommendation
            await self._publish_project_update(project_id, {
                "type": "auto_advance_ready",
                "agent_type": agent_type,
                "next_trigger": next_trigger,
            })

        else:  # human_review | escalate — both queue a review item, differing in priority
            if tier == "human_review":
                priority = 3
                action = "queued_for_review"
                reason = f"Agent confidence {score:.2f} below auto-advance threshold (0.95)"
                logger.info("orchestrator_human_review", project_id=str(project_id), agent_type=agent_type)
            else:
                priority = 5
                action = "escalated"
                reason = f"CRITICAL: Agent confidence {score:.2f} — requires immediate attention"
                logger.warning("orchestrator_escalation", project_id=str(project_id), agent_type=agent_type, score=score)
                await self.event_logger.log_escalation(
                    project_id=project_id,
                    agent_type=agent_type,
                    reason=f"Critical: Agent confidence {score:.2f} below minimum threshold (0.85)",
                )

            queue_item = await self._create_human_review_item(
                project_id=project_id,
                agent_type=agent_type,
                agent_run_id=agent_run_id,
                result=result,
                priority=priority,
                reason=reason,
            )
            decision = await record_decision(
                self.db,
                project_id=project_id,
                agent_type=agent_type,
                action=action,
                confidence_score=score,
                reasoning=self._decision_reasoning(agent_type, agent_run_id, result, tier),
                input_summary={
                    "agent_run_id": str(agent_run_id),
                    "output_keys": sorted(result.output_data.keys()) if isinstance(result.output_data, dict) else [],
                    "errors": result.errors,
                },
                context_package={"context": context, "output_data": result.output_data},
                actor=f"agent:{agent_type}",
                review_queue_item_id=queue_item.id,
            )
            await self._link_decision_to_queue_item(queue_item, decision.id)

            await self.event_logger.log_human_review_queued(
                project_id=project_id,
                agent_type=agent_type,
                queue_item_id=queue_item.id,
                reason=queue_item.reason,
            )
            await self._publish_project_update(project_id, {
                "type": "human_review_queued",
                "queue_item_id": str(queue_item.id),
                "agent_type": agent_type,
                "priority": queue_item.priority,
                "priority_score": round(queue_item.priority_score, 2) if queue_item.priority_score else None,
                "sla_deadline": queue_item.sla_deadline.isoformat() if queue_item.sla_deadline else None,
            })

    @staticmethod
    def _decision_reasoning(
        agent_type: str,
        agent_run_id: uuid.UUID,
        result: AgentResult,
        tier: str,
        next_trigger: Optional[str] = None,
    ) -> str:
        """Compose human-readable, explainable reasoning for a routing decision."""
        summary = json.dumps(result.output_data, sort_keys=True, default=str)
        if len(summary) > 400:
            summary = summary[:400] + "..."
        parts = [
            f"{agent_type} agent run {agent_run_id} finished with status '{result.status}'.",
            f"Confidence {result.confidence_score:.2f} maps to tier '{tier}'"
            f" (auto-advance >= 0.95, human review >= 0.85, escalate below 0.85).",
            f"Output summary: {summary}",
        ]
        if result.errors:
            parts.append(f"Errors: {'; '.join(result.errors[:3])}.")
        if next_trigger:
            parts.append(f"Next lifecycle trigger: '{next_trigger}'.")
        return " ".join(parts)

    async def _link_decision_to_queue_item(
        self, queue_item: HumanReviewQueue, decision_pk: uuid.UUID
    ) -> None:
        """Store the routing decision id on the review item for quick lookup."""
        queue_item.decision_id = decision_pk
        await self.db.commit()

    async def _create_human_review_item(
        self,
        project_id: uuid.UUID,
        agent_type: str,
        agent_run_id: uuid.UUID,
        result: AgentResult,
        priority: int,
        reason: str,
    ) -> HumanReviewQueue:
        """Create a human review queue item with priority scoring. Returns the item."""
        # Priority score = urgency × impact × confidence_gap
        # urgency: 1-5 (from priority)
        # impact: assume 3 for most agent reviews
        # confidence_gap: 0.95 - score
        urgency = priority
        impact = 3
        confidence_gap = max(0, 0.95 - result.confidence_score)
        priority_score = urgency * impact * (1 + confidence_gap * 10)

        # SLA deadline: priority 5 = 4 hours, priority 3 = 24 hours, priority 1 = 72 hours
        sla_hours = {5: 4, 4: 8, 3: 24, 2: 48, 1: 72}.get(priority, 24)
        sla_deadline = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

        queue_item = HumanReviewQueue(
            item_type=QueueItemTypeEnum.agent_review,
            item_id=agent_run_id,
            reason=reason,
            priority=priority,
            priority_score=priority_score,
            sla_deadline=sla_deadline,
            status=QueueStatusEnum.pending,
            context_json={
                "project_id": str(project_id),
                "agent_type": agent_type,
                "agent_run_id": str(agent_run_id),
                "output_summary": result.output_data,
                "errors": result.errors,
            },
            suggested_action=self._suggest_action(agent_type, result),
            confidence_gap=confidence_gap,
        )
        self.db.add(queue_item)
        await self.db.commit()
        await self.db.refresh(queue_item)
        return queue_item

    def _get_next_trigger(self, agent_type: str) -> Optional[str]:
        """Map agent completion to the next logical trigger."""
        mapping = {
            "ingestion": "data_complete",
            "validation": "validation_passed",
            "calculation": "calculation_complete",
            "reporting": "report_approved",
            "vvb_liaison": "registry_approved",
        }
        return mapping.get(agent_type)

    def _suggest_action(self, agent_type: str, result: AgentResult) -> str:
        """Generate a suggested action for the human reviewer."""
        if result.errors:
            return f"Review agent errors and re-run {agent_type} agent after fixes."
        if result.confidence_score < 0.85:
            return f"Investigate low confidence ({result.confidence_score:.2f}) in {agent_type} output. Check data quality."
        return f"Review {agent_type} output for accuracy. Approve if acceptable."

    async def _publish_project_update(self, project_id: uuid.UUID, update: Dict[str, Any]):
        """Publish update via Redis pub/sub for WebSocket forwarding."""
        try:
            await agent_pubsub.publish_project_update(str(project_id), update)
        except Exception as exc:
            logger.error("publish_update_failed", error=str(exc))

    async def _apply_human_review_resolution(
        self,
        item: HumanReviewQueue,
        decision: str,  # "approve" | "reject" | "escalate"
        resolution_notes: str,
        now: datetime,
    ) -> Dict[str, Any]:
        """Apply a resolution to a queue item: mutate, persist, log, notify.

        Shared by human resolution (resolve_human_review) and the SLA
        auto-approve sweep so both produce identical downstream effects.
        """
        item.status = QueueStatusEnum.resolved if decision == "approve" else QueueStatusEnum.escalated
        item.resolution_notes = resolution_notes
        item.human_decision = decision
        item.resolved_at = now

        # Calculate time metrics (created_at may come back tz-naive from SQLite)
        created_at = item.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at:
            item.time_in_queue_seconds = int((now - created_at).total_seconds())
        # response_time would be from assignment to resolution
        if item.assigned_to:
            item.response_time_seconds = item.time_in_queue_seconds

        # Learning feedback: store human decision for confidence calibration
        item.learning_feedback = {
            "human_decision": decision,
            "confidence_gap": item.confidence_gap,
            "agent_type": item.context_json.get("agent_type") if item.context_json else None,
            "resolution_notes": resolution_notes,
        }

        await self.db.commit()

        project_id = item.context_json.get("project_id") if item.context_json else None
        if project_id:
            project_id = uuid.UUID(project_id)
            await self.event_logger.log_human_review_resolved(
                project_id=project_id,
                queue_item_id=item.id,
                decision=decision,
                human_decision=decision,
            )

            # If approved, trigger next agent
            if decision == "approve":
                agent_type = item.context_json.get("agent_type") if item.context_json else None
                next_trigger = self._get_next_trigger(agent_type)
                if next_trigger:
                    await self._publish_project_update(project_id, {
                        "type": "human_review_approved",
                        "queue_item_id": str(item.id),
                        "next_trigger": next_trigger,
                    })

        return {
            "queue_item_id": str(item.id),
            "decision": decision,
            "status": item.status.value,
            "time_in_queue_seconds": item.time_in_queue_seconds,
        }

    async def resolve_human_review(
        self,
        queue_item_id: uuid.UUID,
        decision: str,  # "approve" | "reject" | "escalate"
        resolution_notes: str,
        user_id: uuid.UUID,
        actor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve a human review queue item and trigger follow-up actions."""
        result = await self.db.execute(
            select(HumanReviewQueue).where(HumanReviewQueue.id == queue_item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            return {"error": "Queue item not found"}

        now = datetime.now(timezone.utc)
        resolution = await self._apply_human_review_resolution(item, decision, resolution_notes, now)

        actor_label = actor or str(user_id)
        action = {"approve": "human_approved", "reject": "human_rejected", "escalate": "human_escalated"}.get(
            decision, f"human_{decision}"
        )
        project_id = None
        agent_type = "unknown"
        if item.context_json:
            if item.context_json.get("project_id"):
                project_id = uuid.UUID(item.context_json["project_id"])
            agent_type = item.context_json.get("agent_type") or "unknown"
        await record_decision(
            self.db,
            project_id=project_id,
            agent_type=agent_type,
            action=action,
            confidence_score=None,
            reasoning=(
                f"Human review item {item.id} resolved with decision '{decision}' by {actor_label}. "
                f"Notes: {resolution_notes}"
            ),
            input_summary={
                "queue_item_id": str(item.id),
                "human_decision": decision,
                "confidence_gap": item.confidence_gap,
            },
            actor=actor_label,
            review_queue_item_id=item.id,
        )

        return resolution

    async def sla_auto_approve(
        self,
        queue_item_id: uuid.UUID,
        max_age: Optional[timedelta] = None,
        actor: str = "system:sla_sweep",
        resolution_notes: str = "Auto-approved by 24h SLA sweep",
    ) -> Dict[str, Any]:
        """Auto-approve a stale pending review item. Used by the SLA sweep."""
        result = await self.db.execute(
            select(HumanReviewQueue).where(HumanReviewQueue.id == queue_item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            return {"error": "Queue item not found"}
        if item.status != QueueStatusEnum.pending:
            return {"error": f"Queue item is not pending (status={item.status.value})", "skipped": True}

        now = datetime.now(timezone.utc)
        created_at = item.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age = now - created_at if created_at else timedelta(0)
        if max_age is not None and age < max_age:
            return {"error": "Queue item is younger than the SLA age", "skipped": True}

        resolution = await self._apply_human_review_resolution(item, "approve", resolution_notes, now)

        project_id = None
        agent_type = "unknown"
        if item.context_json:
            if item.context_json.get("project_id"):
                project_id = uuid.UUID(item.context_json["project_id"])
            agent_type = item.context_json.get("agent_type") or "unknown"
        await record_decision(
            self.db,
            project_id=project_id,
            agent_type=agent_type,
            action="sla_auto_approved",
            confidence_score=None,
            reasoning=(
                f"Pending human review item {item.id} was auto-approved after "
                f"{int(age.total_seconds())}s in queue (SLA sweep, human action window expired). "
                f"Original queue reason: {item.reason}"
            ),
            input_summary={
                "queue_item_id": str(item.id),
                "time_in_queue_seconds": item.time_in_queue_seconds,
                "priority": item.priority,
            },
            actor=actor,
            review_queue_item_id=item.id,
        )

        return resolution

    async def get_project_state(self, project_id: uuid.UUID) -> Dict[str, Any]:
        """Get full orchestrator state for a project."""
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return {"error": "Project not found"}

        # Get recent agent runs
        agent_result = await self.db.execute(
            select(AgentRun)
            .where(AgentRun.project_id == project_id)
            .order_by(AgentRun.created_at.desc())
            .limit(10)
        )
        agent_runs = agent_result.scalars().all()

        # Get pending review items
        review_result = await self.db.execute(
            select(HumanReviewQueue)
            .where(
                HumanReviewQueue.item_id.in_([ar.id for ar in agent_runs]),
                HumanReviewQueue.status.in_(["pending", "in_review"]),
            )
        )
        pending_reviews = review_result.scalars().all()

        return {
            "project_id": str(project_id),
            "current_state": project.status.value,
            "agent_runs": [
                {
                    "id": str(ar.id),
                    "agent_type": ar.agent_type.value,
                    "status": ar.status.value,
                    "confidence_score": ar.confidence_score,
                    "execution_time_ms": ar.execution_time_ms,
                    "created_at": ar.created_at.isoformat() if ar.created_at else None,
                }
                for ar in agent_runs
            ],
            "pending_reviews": [
                {
                    "id": str(pr.id),
                    "reason": pr.reason,
                    "priority": pr.priority,
                    "priority_score": pr.priority_score,
                    "sla_deadline": pr.sla_deadline.isoformat() if pr.sla_deadline else None,
                    "suggested_action": pr.suggested_action,
                }
                for pr in pending_reviews
            ],
        }
