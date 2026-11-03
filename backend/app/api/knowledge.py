"""Methodology knowledge base API: ingest, list, fetch, delete, search, RAG query.

Mounted at ``/api/v1/knowledge``. Read endpoints require viewer; document
ingestion requires operator; deletion requires admin.

Route ordering: the static ``/query`` and ``/search`` routes are declared
before the parameterized ``/documents/{document_id}`` route.
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_operator, require_viewer
from app.database import get_db
from app.knowledge.service import KnowledgeBaseService

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class DocumentIngestRequest(BaseModel):
    registry: str = Field(..., pattern="^(gold_standard|verra|ipcc|other)$")
    methodology_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1, max_length=50)
    source_url: Optional[str] = Field(default=None, max_length=1000)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    registry: Optional[str] = None


def _service(db: AsyncSession) -> KnowledgeBaseService:
    return KnowledgeBaseService(db)


@router.post("/documents", status_code=201)
async def ingest_document(
    payload: DocumentIngestRequest,
    current_user=Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Ingest (or idempotently replace) a methodology document."""
    service = _service(db)
    document = await service.ingest_document(
        registry=payload.registry,
        methodology_id=payload.methodology_id,
        title=payload.title,
        content=payload.content,
        version=payload.version,
        source_url=payload.source_url,
        metadata=payload.metadata,
    )
    detail = await service.get_document(document.id)
    return detail


@router.get("/documents")
async def list_documents(
    registry: Optional[str] = None,
    current_user=Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """List ingested methodology documents, optionally filtered by registry."""
    return {"documents": await _service(db).list_documents(registry=registry)}


@router.post("/query")
async def query_knowledge(
    payload: KnowledgeQueryRequest,
    current_user=Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """RAG answer over the methodology knowledge base."""
    return await _service(db).query_knowledge_base(
        payload.question, registry=payload.registry, k=4
    )


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., min_length=1),
    registry: Optional[str] = None,
    k: int = Query(5, ge=1, le=50),
    current_user=Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Vector-search knowledge chunks."""
    return {"results": await _service(db).search(q, registry=registry, k=k)}


@router.get("/documents/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    current_user=Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single document with its chunks."""
    detail = await _service(db).get_document(document_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return detail


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its chunks (admin only)."""
    deleted = await _service(db).delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


__all__: List[str] = ["router"]
