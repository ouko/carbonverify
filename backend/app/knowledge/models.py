"""ORM models for the methodology knowledge base (Phase 5).

Defined package-locally (like ``app.remediation.models``) on the shared
``Base`` from ``app.database``. Columns use dialect-portable types —
``sa.Uuid`` renders as ``UUID`` on PostgreSQL and CHAR(32) on SQLite, and the
JSON column variant-renders as ``JSONB`` on PostgreSQL — so the test suite's
SQLite ``create_all`` works without conftest type patching. The hand-authored
Alembic migration is the source of truth for PostgreSQL DDL.

``metadata`` is a reserved attribute on declarative classes, so the document
metadata JSONB column is exposed as ``metadata_`` (column name ``metadata``).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite test compatibility).
PortableJSONB = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MethodologyDocument(Base):
    """A methodology text (chunked concatenation or full text) ingested for RAG.

    ``registry`` is one of ``gold_standard`` | ``verra`` | ``ipcc`` | ``other``.
    Re-ingesting the same ``registry`` + ``methodology_id`` + ``version``
    replaces the existing document and its chunks idempotently.
    """

    __tablename__ = "methodology_documents"

    __table_args__ = (
        Index("ix_methodology_documents_registry", "registry"),
        Index("ix_methodology_documents_methodology_id", "methodology_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    registry: Mapped[str] = mapped_column(String(50), nullable=False)
    methodology_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata", PortableJSONB, default=dict, nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    chunks: Mapped[List["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index",
    )


class KnowledgeChunk(Base):
    """A searchable chunk of a methodology document with a stored embedding."""

    __tablename__ = "knowledge_chunks"

    __table_args__ = (
        Index("ix_knowledge_chunks_document_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("methodology_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(PortableJSONB, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    document: Mapped[MethodologyDocument] = relationship(
        "MethodologyDocument", back_populates="chunks"
    )
