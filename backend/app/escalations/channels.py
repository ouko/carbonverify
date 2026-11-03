"""Notification channel adapters for escalation events.

Every adapter is no-op-safe: without credentials or configuration it reports
itself as not configured (log-only) instead of raising. The service records
each attempt (success or failure) on the event's ``channels_sent`` map; a
failing channel must never break dispatch of the others.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class ChannelResult:
    """Outcome of a single channel dispatch attempt."""

    channel: str
    success: bool
    configured: bool
    detail: str = ""
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_record(self) -> Dict[str, Any]:
        return {
            "sent_at": self.sent_at.isoformat(),
            "success": self.success,
            "configured": self.configured,
            "detail": self.detail,
        }


class ChannelAdapter(Protocol):
    name: str

    async def send(self, event: Any) -> ChannelResult: ...


def _render_text(event: Any) -> str:
    return f"[{event.source}] {event.title}\n\n{event.detail}"


class WhatsAppChannel:
    """Outbound WhatsApp alert via the Meta WhatsApp Business API.

    Log-only when WhatsApp credentials or the operator recipient are missing.
    """

    name = "whatsapp"

    async def send(self, event: Any) -> ChannelResult:
        recipient = settings.ESCALATION_NOTIFY_WHATSAPP
        token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        if not (recipient and token and phone_number_id):
            logger.info(
                "escalation_whatsapp_not_configured",
                escalation_id=str(event.id),
            )
            return ChannelResult(
                channel=self.name,
                success=False,
                configured=False,
                detail="WhatsApp credentials or recipient not configured",
            )
        try:
            from app.services.whatsapp.meta_api import get_whatsapp_api

            outcome = await get_whatsapp_api().send_text_message(
                to=recipient,
                text=_render_text(event),
            )
            success = bool(outcome.get("success"))
            return ChannelResult(
                channel=self.name,
                success=success,
                configured=True,
                detail="" if success else str(outcome.get("error", "send failed")),
            )
        except Exception as exc:  # noqa: BLE001 — never raise on channel failure
            logger.error("escalation_whatsapp_send_failed", escalation_id=str(event.id), error=str(exc))
            return ChannelResult(channel=self.name, success=False, configured=True, detail=str(exc))


class SMSChannel:
    """SMS alert via a pluggable HTTP webhook (provider-agnostic).

    Log-only when ``ESCALATION_SMS_WEBHOOK_URL`` / ``ESCALATION_NOTIFY_SMS``
    are not configured.
    """

    name = "sms"

    async def send(self, event: Any) -> ChannelResult:
        webhook = settings.ESCALATION_SMS_WEBHOOK_URL
        recipient = settings.ESCALATION_NOTIFY_SMS
        if not (webhook and recipient):
            logger.info("escalation_sms_not_configured", escalation_id=str(event.id))
            return ChannelResult(
                channel=self.name,
                success=False,
                configured=False,
                detail="SMS webhook or recipient not configured",
            )
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    webhook,
                    json={"to": recipient, "message": _render_text(event)},
                )
                response.raise_for_status()
            return ChannelResult(channel=self.name, success=True, configured=True)
        except Exception as exc:  # noqa: BLE001 — never raise on channel failure
            logger.error("escalation_sms_send_failed", escalation_id=str(event.id), error=str(exc))
            return ChannelResult(channel=self.name, success=False, configured=True, detail=str(exc))


class EmailChannel:
    """Email alert via the existing EmailService (SES primary, SMTP fallback)."""

    name = "email"

    def is_configured(self) -> bool:
        recipients = settings.ESCALATION_NOTIFY_EMAIL
        if not recipients:
            return False
        if settings.EMAIL_PROVIDER.lower() == "smtp":
            return bool(settings.SMTP_HOST)
        return True  # SES provider assumed configured via IAM role

    async def send(self, event: Any) -> ChannelResult:
        recipients = settings.ESCALATION_NOTIFY_EMAIL
        if not self.is_configured():
            logger.info("escalation_email_not_configured", escalation_id=str(event.id))
            return ChannelResult(
                channel=self.name,
                success=False,
                configured=False,
                detail="Email recipient or SMTP/SES config missing",
            )
        try:
            from app.services.email import get_email_service

            service = get_email_service()
            for recipient in [r.strip() for r in recipients.split(",") if r.strip()]:
                await service.send_email(
                    to=recipient,
                    subject=f"[Escalation P{event.priority}] {event.title}",
                    body_text=_render_text(event),
                )
            return ChannelResult(channel=self.name, success=True, configured=True)
        except Exception as exc:  # noqa: BLE001 — never raise on channel failure
            logger.error("escalation_email_send_failed", escalation_id=str(event.id), error=str(exc))
            return ChannelResult(channel=self.name, success=False, configured=True, detail=str(exc))


class InAppChannel:
    """Realtime in-app push over the orchestrator pub/sub → /ws/notifications.

    Reuses the ``agent_escalation`` event shape the frontend
    ``notificationStore`` / ``useCommandWebSocket`` already render.
    """

    name = "in_app"

    async def send(self, event: Any) -> ChannelResult:
        try:
            from app.orchestrator.pubsub import agent_pubsub

            await agent_pubsub.publish_event(
                "agent_escalation",
                {
                    "escalation_id": str(event.id),
                    "agent_type": event.source,
                    "project_id": str(event.project_id) if event.project_id else None,
                    "title": event.title,
                    "detail": event.detail,
                    "priority": event.priority,
                    "severity": event.severity_score,
                },
            )
            return ChannelResult(channel=self.name, success=True, configured=True)
        except Exception as exc:  # noqa: BLE001 — never raise on channel failure
            logger.error("escalation_in_app_push_failed", escalation_id=str(event.id), error=str(exc))
            return ChannelResult(channel=self.name, success=False, configured=True, detail=str(exc))


_adapters: Optional[Dict[str, ChannelAdapter]] = None


def get_channel_adapters() -> Dict[str, ChannelAdapter]:
    """Lazy registry of channel adapters (single instance per process)."""
    global _adapters
    if _adapters is None:
        _adapters = {
            adapter.name: adapter
            for adapter in (WhatsAppChannel(), SMSChannel(), EmailChannel(), InAppChannel())
        }
    return _adapters
