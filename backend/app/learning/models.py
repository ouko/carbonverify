"""ORM models for the agent learning loop (Phase 5).

Defined package-locally on the shared ``Base`` from ``app.database`` with
dialect-portable column types (see ``app.knowledge.models`` for the rationale).
The Alembic migration is the source of truth for PostgreSQL DDL.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import JSON, DateTime, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite test compatibility).
PortableJSONB = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LearningReport(Base):
    """A persisted, structured learning-loop report (e.g. weekly retraining brief)."""

    __tablename__ = "learning_reports"

    __table_args__ = (
        Index("ix_learning_reports_report_type", "report_type"),
        Index("ix_learning_reports_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # e.g. "weekly_retraining"
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    report: Mapped[Dict[str, Any]] = mapped_column(PortableJSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
