"""Methodology knowledge base: vector search + RAG over methodology texts.

Module-level ``query_knowledge_base`` / ``search_knowledge`` wrappers open
their own DB session so external consumers (e.g. the remediation rule
``vvb_clarification → kb_draft_response``) can call them with just a query
string. Both are fully defensive: any failure logs and returns ``None`` /
``[]`` rather than raising, so callers never break on knowledge-base errors.
"""

from typing import Any

from app.core.logging import get_logger
from app.knowledge.embeddings import (
    Embedder,
    LocalHashEmbedder,
    OpenAICompatibleEmbedder,
    get_embedder,
    top_k,
)
from app.knowledge.models import KnowledgeChunk, MethodologyDocument
from app.knowledge.service import KnowledgeBaseService, chunk_text

logger = get_logger(__name__)

__all__ = [
    "Embedder",
    "KnowledgeBaseService",
    "KnowledgeChunk",
    "LocalHashEmbedder",
    "MethodologyDocument",
    "OpenAICompatibleEmbedder",
    "chunk_text",
    "get_embedder",
    "query_knowledge_base",
    "search_knowledge",
    "top_k",
]


async def search_knowledge(
    query: str,
    registry: str | None = None,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Module-level vector search using a standalone DB session."""
    try:
        from app.database import get_db_context

        async with get_db_context() as db:
            service = KnowledgeBaseService(db)
            return await service.search(query, registry=registry, k=k)
    except Exception as exc:  # noqa: BLE001 — knowledge base must never break callers
        logger.warning("search_knowledge_failed", error=str(exc))
        return []


async def query_knowledge_base(
    question: str,
    registry: str | None = None,
    k: int = 4,
) -> dict[str, Any] | None:
    """Module-level RAG query using a standalone DB session."""
    try:
        from app.database import get_db_context

        async with get_db_context() as db:
            service = KnowledgeBaseService(db)
            return await service.query_knowledge_base(question, registry=registry, k=k)
    except Exception as exc:  # noqa: BLE001 — knowledge base must never break callers
        logger.warning("query_knowledge_base_failed", error=str(exc))
        return None
