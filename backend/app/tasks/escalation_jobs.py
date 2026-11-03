"""Celery jobs for the human escalation & notification service.

- ``dispatch_p0_escalations`` (60s beat): re-send P0 events that still have no
  successful channel within the last 60s.
- ``send_p1_escalations`` (30min beat or SLA-scheduled): dispatch email +
  in-app channels for open P1 events.
- ``daily_escalation_digest`` (daily beat): aggregate open P2 plus the last
  24h of P0/P1 into a single digest email.

DB access goes through ``app.database.get_db_context`` (lazy import at call
time) so tests can route sessions via the ``patch_db_context`` fixture.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app import database as app_database
from app.core.logging import get_logger
from app.escalations.models import EscalationEvent, EscalationStatus
from app.escalations.service import (
    P0_REDELIVER_WINDOW,
    EscalationService,
    _utcnow,
)
from app.tasks.celery_app import celery_app
from app.tasks.jobs import run_async

logger = get_logger(__name__)

P0_BATCH_LIMIT = 25
P1_BATCH_LIMIT = 50


def _latest_success(event: EscalationEvent) -> datetime | None:
    """Most recent successful channel send for an event, or None."""
    latest: datetime | None = None
    for record in (event.channels_sent or {}).values():
        if not record.get("success"):
            continue
        raw = record.get("sent_at")
        if not raw:
            continue
        try:
            sent_at = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=UTC)
        if latest is None or sent_at > latest:
            latest = sent_at
    return latest


@celery_app.task(bind=True, max_retries=3)
def dispatch_p0_escalations(self):
    """Re-dispatch open P0 events with no successful channel in the last 60s."""
    async def _work():
        redispatched = 0
        async with app_database.get_db_context() as db:
            service = EscalationService(db)
            result = await db.execute(
                select(EscalationEvent)
                .where(
                    EscalationEvent.priority == 0,
                    EscalationEvent.status == EscalationStatus.open,
                )
                .order_by(EscalationEvent.created_at.asc())
                .limit(P0_BATCH_LIMIT)
            )
            events = result.scalars().all()
            cutoff = _utcnow() - P0_REDELIVER_WINDOW
            for event in events:
                latest = _latest_success(event)
                if latest is not None and latest >= cutoff:
                    continue
                await service.dispatch(event)
                redispatched += 1
                logger.info("escalation_p0_redispatched", escalation_id=str(event.id))
        return {"checked": len(events), "redispatched": redispatched}

    try:
        return run_async(_work())
    except Exception as exc:
        logger.error("dispatch_p0_escalations_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_p1_escalations(self, event_id: str | None = None):
    """Dispatch email + in-app channels for open P1 escalations.

    When ``event_id`` is given (SLA-scheduled by the service), only that event
    is considered; the beat job sweeps all unsent open P1 events.
    """
    async def _work():
        dispatched = 0
        async with app_database.get_db_context() as db:
            service = EscalationService(db)
            stmt = (
                select(EscalationEvent)
                .where(
                    EscalationEvent.priority == 1,
                    EscalationEvent.status == EscalationStatus.open,
                )
                .order_by(EscalationEvent.created_at.asc())
                .limit(P1_BATCH_LIMIT)
            )
            if event_id:
                stmt = select(EscalationEvent).where(EscalationEvent.id == uuid.UUID(event_id))
            result = await db.execute(stmt)
            events = result.scalars().all()
            for event in events:
                if event.status != EscalationStatus.open:
                    continue
                sent = event.channels_sent or {}
                already_sent = any(
                    record.get("success") for record in sent.values()
                )
                if already_sent and event_id is None:
                    continue  # beat sweep only retries unsent events
                await service.dispatch(event, channels=["email", "in_app"])
                dispatched += 1
                logger.info("escalation_p1_dispatched", escalation_id=str(event.id))
        return {"checked": len(events), "dispatched": dispatched}

    try:
        return run_async(_work())
    except Exception as exc:
        logger.error("send_p1_escalations_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(bind=True, max_retries=3)
def daily_escalation_digest(self):
    """Aggregate open P2 + the last 24h of P0/P1 into one digest email."""
    async def _work():
        async with app_database.get_db_context() as db:
            now = _utcnow()
            day_ago = now - timedelta(hours=24)

            open_result = await db.execute(
                select(EscalationEvent).where(EscalationEvent.status == EscalationStatus.open)
            )
            open_events = open_result.scalars().all()

            recent_result = await db.execute(
                select(EscalationEvent).where(
                    EscalationEvent.created_at >= day_ago,
                    EscalationEvent.priority.in_([0, 1]),
                )
            )
            recent_events = recent_result.scalars().all()

            open_p2 = [e for e in open_events if e.priority == 2]
            open_p1 = [e for e in open_events if e.priority == 1]
            open_p0 = [e for e in open_events if e.priority == 0]
            recent_p0 = [e for e in recent_events if e.priority == 0]
            recent_p1 = [e for e in recent_events if e.priority == 1]

            lines = [
                "CarbonVerify escalation digest",
                f"Generated: {now.isoformat()}",
                "",
                f"Open P0 (realtime): {len(open_p0)}",
                f"Open P1: {len(open_p1)}",
                f"Open P2 (digest-only): {len(open_p2)}",
                f"Last 24h P0 raised: {len(recent_p0)}",
                f"Last 24h P1 raised: {len(recent_p1)}",
                "",
            ]
            for event in open_events:
                lines.append(
                    f"- [P{event.priority}] {event.title} ({event.source}, status={event.status.value}, id={event.id})"
                )
            digest_text = "\n".join(lines)

            email_sent = False
            from app.config import get_settings

            settings = get_settings()
            if settings.ESCALATION_NOTIFY_EMAIL:
                try:
                    from app.services.email import get_email_service

                    service = get_email_service()
                    for recipient in [
                        r.strip() for r in settings.ESCALATION_NOTIFY_EMAIL.split(",") if r.strip()
                    ]:
                        await service.send_email(
                            to=recipient,
                            subject=f"Escalation digest — {len(open_events)} open, "
                                    f"{len(recent_p0) + len(recent_p1)} raised in 24h",
                            body_text=digest_text,
                        )
                    email_sent = True
                except Exception as exc:  # noqa: BLE001 — digest email is best-effort
                    logger.error("escalation_digest_email_failed", error=str(exc))

            logger.info(
                "escalation_digest_generated",
                open_total=len(open_events),
                recent_p0=len(recent_p0),
                recent_p1=len(recent_p1),
                email_sent=email_sent,
            )
            return {
                "open_p0": len(open_p0),
                "open_p1": len(open_p1),
                "open_p2": len(open_p2),
                "recent_24h_p0": len(recent_p0),
                "recent_24h_p1": len(recent_p1),
                "email_sent": email_sent,
            }

    try:
        return run_async(_work())
    except Exception as exc:
        logger.error("daily_escalation_digest_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)
