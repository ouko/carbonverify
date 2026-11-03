"""EscalationService: raise, dispatch, acknowledge, and resolve escalations.

Priority model:
  P0 (0) — realtime: dispatch all channels immediately, beat job re-sends
           every 60s until a channel succeeds.
  P1 (1) — near-realtime: in-app push now, email + remaining channels via the
           30-minute beat job (2h SLA tracking from creation).
  P2 (2) — digest only: aggregated into the daily digest job.

Channel failures are recorded on ``channels_sent`` and never raised.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.escalations.channels import (
    ChannelAdapter,
    get_channel_adapters,
)
from app.escalations.models import EscalationEvent, EscalationStatus
from app.orchestrator.audit_chain import record_decision
from app.orchestrator.pubsub import agent_pubsub

logger = get_logger(__name__)

PRIORITY_P0 = 0
PRIORITY_P1 = 1
PRIORITY_P2 = 2

P1_SLA = timedelta(hours=2)
P0_REDELIVER_WINDOW = timedelta(seconds=60)

# Channels attempted per priority on dispatch.
PRIORITY_CHANNELS: Dict[int, List[str]] = {
    PRIORITY_P0: ["whatsapp", "sms", "email", "in_app"],
    PRIORITY_P1: ["email", "in_app"],
    PRIORITY_P2: [],
}


def derive_priority(severity_score: float) -> int:
    """Map a 0-1 severity score to P0/P1/P2."""
    if severity_score >= 0.9:
        return PRIORITY_P0
    if severity_score >= 0.7:
        return PRIORITY_P1
    return PRIORITY_P2


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EscalationService:
    """Business logic for escalation events. All methods are defensive."""

    def __init__(
        self,
        db: AsyncSession,
        adapters: Optional[Dict[str, ChannelAdapter]] = None,
    ):
        self.db = db
        self._adapters = adapters

    def _get_adapters(self) -> Dict[str, ChannelAdapter]:
        if self._adapters is None:
            self._adapters = get_channel_adapters()
        return self._adapters

    async def raise_escalation(
        self,
        source: str,
        title: str,
        detail: str,
        context_package: Optional[Dict[str, Any]] = None,
        priority: Optional[int] = None,
        project_id: Optional[uuid.UUID] = None,
        severity_score: Optional[float] = None,
    ) -> EscalationEvent:
        """Create an escalation event and dispatch it according to priority."""
        if severity_score is None:
            severity_score = 0.5
        severity_score = max(0.0, min(1.0, float(severity_score)))
        if priority is None:
            priority = derive_priority(severity_score)
        if priority not in (PRIORITY_P0, PRIORITY_P1, PRIORITY_P2):
            raise ValueError(f"Invalid escalation priority: {priority}")

        event = EscalationEvent(
            project_id=project_id,
            source=source,
            title=title,
            detail=detail,
            context_package=context_package or {},
            priority=priority,
            severity_score=severity_score,
            status=EscalationStatus.open,
            channels_sent={},
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        logger.info(
            "escalation_raised",
            escalation_id=str(event.id),
            source=source,
            priority=priority,
            severity_score=severity_score,
        )

        await self.dispatch(event)

        if priority == PRIORITY_P1:
            self._schedule_p1_sla(str(event.id))

        return event

    async def dispatch(
        self,
        event: EscalationEvent,
        channels: Optional[List[str]] = None,
    ) -> EscalationEvent:
        """Attempt each configured channel, recording every attempt."""
        channel_names = channels if channels is not None else PRIORITY_CHANNELS.get(event.priority, [])
        adapters = self._get_adapters()
        sent: Dict[str, Any] = dict(event.channels_sent or {})
        for name in channel_names:
            adapter = adapters.get(name)
            if adapter is None:
                continue
            try:
                result = await adapter.send(event)
                record = result.to_record()
            except Exception as exc:  # noqa: BLE001 — never raise on channel failure
                logger.error(
                    "escalation_channel_crashed",
                    escalation_id=str(event.id),
                    channel=name,
                    error=str(exc),
                )
                record = {
                    "sent_at": _utcnow().isoformat(),
                    "success": False,
                    "configured": True,
                    "detail": f"adapter crashed: {exc}",
                }
            sent[name] = record
            logger.info(
                "escalation_channel_attempt",
                escalation_id=str(event.id),
                channel=name,
                success=record["success"],
                configured=record["configured"],
            )
        # Assign a fresh dict so SQLAlchemy dirty-detection fires without
        # MutableDict (keeps the model simple across dialects).
        event.channels_sent = sent
        await self.db.commit()
        return event

    def _schedule_p1_sla(self, event_id: str) -> None:
        """Hand P1 events to Celery for SLA-tracked channel dispatch.

        Skipped under eager mode (tests) where beat/worker scheduling is a
        no-op and get_db_context is monkeypatched per test.
        """
        try:
            from app.tasks.celery_app import celery_app

            if celery_app.conf.task_always_eager:
                return
            from app.tasks.escalation_jobs import send_p1_escalations

            send_p1_escalations.apply_async(args=[event_id], countdown=int(P1_SLA.total_seconds()))
            logger.info("escalation_p1_sla_scheduled", escalation_id=event_id, sla_seconds=int(P1_SLA.total_seconds()))
        except Exception as exc:  # noqa: BLE001 — scheduling is best-effort
            logger.warning("escalation_p1_sla_schedule_failed", escalation_id=event_id, error=str(exc))

    async def get_event(self, event_id: uuid.UUID) -> Optional[EscalationEvent]:
        result = await self.db.execute(select(EscalationEvent).where(EscalationEvent.id == event_id))
        return result.scalar_one_or_none()

    async def acknowledge(self, event_id: uuid.UUID, user_id: uuid.UUID) -> EscalationEvent:
        """Mark an escalation as acknowledged by a human operator."""
        event = await self.get_event(event_id)
        if event is None:
            raise ValueError("Escalation event not found")
        if event.status == EscalationStatus.resolved:
            raise ValueError("Escalation event is already resolved")

        event.status = EscalationStatus.acknowledged
        event.acknowledged_at = _utcnow()
        event.acknowledged_by = user_id
        await self.db.commit()

        await record_decision(
            self.db,
            agent_type="system:escalation",
            action="escalation_acknowledged",
            confidence_score=None,
            reasoning=f"Escalation {event.id} ('{event.title}') acknowledged by human:{user_id}.",
            input_summary={
                "escalation_id": str(event.id),
                "source": event.source,
                "priority": event.priority,
                "severity_score": event.severity_score,
            },
            actor=f"human:{user_id}",
        )
        await self._publish_lifecycle_event("escalation_acknowledged", event)
        return event

    async def resolve(
        self,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        notes: str,
    ) -> EscalationEvent:
        """Resolve an escalation with human notes."""
        event = await self.get_event(event_id)
        if event is None:
            raise ValueError("Escalation event not found")
        if event.status == EscalationStatus.resolved:
            raise ValueError("Escalation event is already resolved")

        now = _utcnow()
        event.status = EscalationStatus.resolved
        if event.acknowledged_at is None:
            event.acknowledged_at = now
            event.acknowledged_by = user_id
        event.resolved_at = now
        event.resolved_by = user_id
        event.resolution_notes = notes
        await self.db.commit()

        await record_decision(
            self.db,
            agent_type="system:escalation",
            action="escalation_resolved",
            confidence_score=None,
            reasoning=(
                f"Escalation {event.id} ('{event.title}') resolved by human:{user_id}. "
                f"Notes: {notes}"
            ),
            input_summary={
                "escalation_id": str(event.id),
                "source": event.source,
                "priority": event.priority,
                "severity_score": event.severity_score,
                "resolution_notes": notes,
            },
            actor=f"human:{user_id}",
        )
        await self._publish_lifecycle_event("escalation_resolved", event)
        return event

    async def _publish_lifecycle_event(self, event_type: str, event: EscalationEvent) -> None:
        """Publish an ack/resolve notification for /ws/notifications clients."""
        try:
            await agent_pubsub.publish_event(
                event_type,
                {
                    "escalation_id": str(event.id),
                    "agent_type": event.source,
                    "project_id": str(event.project_id) if event.project_id else None,
                    "title": event.title,
                    "priority": event.priority,
                    "status": event.status.value,
                },
            )
        except Exception as exc:  # noqa: BLE001 — notification must not break state changes
            logger.error("escalation_lifecycle_publish_failed", escalation_id=str(event.id), error=str(exc))
