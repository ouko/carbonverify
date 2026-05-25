"""Event logging and audit trail for the orchestrator."""

import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import OrchestratorEvent, OrchestratorEventTypeEnum
from app.core.logging import get_logger

logger = get_logger(__name__)


class EventLogger:
    """Comprehensive event logging for audit trails."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_state_transition(
        self,
        project_id: uuid.UUID,
        from_state: str,
        to_state: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorEvent:
        event = OrchestratorEvent(
            project_id=project_id,
            event_type=OrchestratorEventTypeEnum.state_transition,
            from_state=from_state,
            to_state=to_state,
            details=details or {},
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(
            "state_transition",
            project_id=str(project_id),
            from_state=from_state,
            to_state=to_state,
        )
        return event

    async def log_agent_dispatch(
        self,
        project_id: uuid.UUID,
        agent_type: str,
        trigger_event: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorEvent:
        event = OrchestratorEvent(
            project_id=project_id,
            event_type=OrchestratorEventTypeEnum.agent_dispatch,
            details={"agent_type": agent_type, "trigger": trigger_event, **(details or {})},
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(
            "agent_dispatch",
            project_id=str(project_id),
            agent_type=agent_type,
            trigger=trigger_event,
        )
        return event

    async def log_agent_complete(
        self,
        project_id: uuid.UUID,
        agent_run_id: uuid.UUID,
        confidence_score: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorEvent:
        event = OrchestratorEvent(
            project_id=project_id,
            event_type=OrchestratorEventTypeEnum.agent_complete,
            agent_run_id=agent_run_id,
            confidence_score=confidence_score,
            details=details or {},
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(
            "agent_complete",
            project_id=str(project_id),
            agent_run_id=str(agent_run_id),
            confidence=confidence_score,
        )
        return event

    async def log_confidence_check(
        self,
        project_id: uuid.UUID,
        agent_type: str,
        confidence_score: float,
        decision: str,  # auto_advance | human_review | escalate
        details: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorEvent:
        event = OrchestratorEvent(
            project_id=project_id,
            event_type=OrchestratorEventTypeEnum.confidence_check,
            confidence_score=confidence_score,
            details={"agent_type": agent_type, "decision": decision, **(details or {})},
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(
            "confidence_check",
            project_id=str(project_id),
            agent_type=agent_type,
            confidence=confidence_score,
            decision=decision,
        )
        return event

    async def log_human_review_queued(
        self,
        project_id: uuid.UUID,
        agent_type: str,
        queue_item_id: uuid.UUID,
        reason: str,
    ) -> OrchestratorEvent:
        event = OrchestratorEvent(
            project_id=project_id,
            event_type=OrchestratorEventTypeEnum.human_review_queued,
            details={"agent_type": agent_type, "queue_item_id": str(queue_item_id), "reason": reason},
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(
            "human_review_queued",
            project_id=str(project_id),
            agent_type=agent_type,
            queue_item_id=str(queue_item_id),
            reason=reason,
        )
        return event

    async def log_human_review_resolved(
        self,
        project_id: uuid.UUID,
        queue_item_id: uuid.UUID,
        decision: str,
        human_decision: str,
    ) -> OrchestratorEvent:
        event = OrchestratorEvent(
            project_id=project_id,
            event_type=OrchestratorEventTypeEnum.human_review_resolved,
            details={"queue_item_id": str(queue_item_id), "decision": decision, "human_decision": human_decision},
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(
            "human_review_resolved",
            project_id=str(project_id),
            queue_item_id=str(queue_item_id),
            decision=decision,
            human_decision=human_decision,
        )
        return event

    async def log_auto_advance(
        self,
        project_id: uuid.UUID,
        from_state: str,
        to_state: str,
        agent_type: str,
    ) -> OrchestratorEvent:
        event = OrchestratorEvent(
            project_id=project_id,
            event_type=OrchestratorEventTypeEnum.auto_advance,
            from_state=from_state,
            to_state=to_state,
            details={"agent_type": agent_type},
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(
            "auto_advance",
            project_id=str(project_id),
            from_state=from_state,
            to_state=to_state,
            agent_type=agent_type,
        )
        return event

    async def log_escalation(
        self,
        project_id: uuid.UUID,
        agent_type: str,
        reason: str,
    ) -> OrchestratorEvent:
        event = OrchestratorEvent(
            project_id=project_id,
            event_type=OrchestratorEventTypeEnum.escalation,
            details={"agent_type": agent_type, "reason": reason},
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(
            "escalation",
            project_id=str(project_id),
            agent_type=agent_type,
            reason=reason,
        )
        return event

    async def get_event_history(
        self,
        project_id: uuid.UUID,
        limit: int = 100,
    ) -> list:
        result = await self.db.execute(
            select(OrchestratorEvent)
            .where(OrchestratorEvent.project_id == project_id)
            .order_by(OrchestratorEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
