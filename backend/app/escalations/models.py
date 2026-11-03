"""ORM models for the human escalation & notification service."""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EscalationStatus(str, PyEnum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class EscalationEvent(Base):
    """A human-intervention event raised by an agent or system component.

    Priorities: 0 = P0 (realtime), 1 = P1 (near-realtime), 2 = P2 (digest).
    ``channels_sent`` maps channel name ->
    ``{"sent_at": iso, "success": bool, "configured": bool, "detail": str}``.
    """

    __tablename__ = "escalation_events"

    __table_args__ = (
        Index("ix_escalation_events_project_id", "project_id"),
        Index("ix_escalation_events_status", "status"),
        Index("ix_escalation_events_priority", "priority"),
        Index("ix_escalation_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    # agent_type (e.g. "validation") or a system source (e.g. "system:remediation")
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    context_package: Mapped[dict] = mapped_column(JSONB, default=dict)
    # 0 = P0 realtime, 1 = P1, 2 = P2 digest
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[EscalationStatus] = mapped_column(
        Enum(EscalationStatus, name="escalation_event_status"),
        default=EscalationStatus.open,
        nullable=False,
    )
    channels_sent: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
