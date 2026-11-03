"""Database models for the shared self-healing remediation engine.

Defined package-locally (like ``app.validation_engine.models``) on the shared
``Base`` from ``app.database``. Columns use dialect-portable types —
``sa.Uuid`` renders as ``UUID`` on PostgreSQL and CHAR(32) on SQLite, and the
JSON column variant-renders as ``JSONB`` on PostgreSQL — so the test suite's
SQLite ``create_all`` works without conftest type patching. The hand-authored
Alembic migration is the source of truth for PostgreSQL DDL.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite test compatibility).
PortableJSONB = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class RemediationRule(Base):
    """A named remediation strategy for a failure category."""

    __tablename__ = "remediation_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(PortableJSONB, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class RemediationAttempt(Base):
    """One persisted attempt to remediate a failing target."""

    __tablename__ = "remediation_attempts"

    __table_args__ = (
        Index("ix_remediation_attempts_rule_key", "rule_key"),
        Index("ix_remediation_attempts_target", "target_type", "target_id"),
        Index("ix_remediation_attempts_status", "status"),
        Index("ix_remediation_attempts_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # attempted | resolved | failed | escalated
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="attempted")
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # SHA-256 of the canonical JSON of the failing state before the attempt.
    before_state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # SHA-256 of the state after the attempt (null if unchanged/unavailable).
    after_state_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # What was tried and the result; carries a failing_state snapshot so the
    # remediation sweep / manual retry can re-run the attempt later.
    detail: Mapped[dict[str, Any]] = mapped_column(PortableJSONB, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
