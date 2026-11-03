"""KnowledgeBaseService: ingest, chunk, embed, search, and RAG-query methodology texts."""

from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.knowledge.embeddings import Embedder, get_embedder, top_k
from app.knowledge.models import KnowledgeChunk, MethodologyDocument

logger = get_logger(__name__)

CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50

RAG_ANSWER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "Synthesized answer grounded in the provided passages.",
        },
        "citations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Methodology IDs cited, e.g. ['GS TPDD v3'].",
        },
    },
    "required": ["answer", "citations"],
}


def chunk_text(content: str, size: int = CHUNK_SIZE_TOKENS, overlap: int = CHUNK_OVERLAP_TOKENS) -> List[str]:
    """Split text into token windows with overlap using a whitespace splitter."""
    tokens = content.split()
    if not tokens:
        return []
    if len(tokens) <= size:
        return [" ".join(tokens)]
    step = max(1, size - overlap)
    chunks = []
    for start in range(0, len(tokens), step):
        window = tokens[start : start + size]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + size >= len(tokens):
            break
    return chunks


def _document_to_dict(doc: MethodologyDocument) -> Dict[str, Any]:
    return {
        "id": str(doc.id),
        "registry": doc.registry,
        "methodology_id": doc.methodology_id,
        "title": doc.title,
        "version": doc.version,
        "source_url": doc.source_url,
        "metadata": doc.metadata_ or {},
        "ingested_at": doc.ingested_at.isoformat() if doc.ingested_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def _chunk_to_dict(chunk: KnowledgeChunk) -> Dict[str, Any]:
    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "token_count": chunk.token_count,
    }


class KnowledgeBaseService:
    """Ingest and retrieve methodology knowledge with vector search + RAG."""

    def __init__(self, db: AsyncSession, embedder: Optional[Embedder] = None):
        self.db = db
        self.embedder = embedder or get_embedder()

    async def ingest_document(
        self,
        registry: str,
        methodology_id: str,
        title: str,
        content: str,
        version: str,
        source_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MethodologyDocument:
        """Ingest a methodology document, chunking + embedding it for search.

        Idempotent per ``(registry, methodology_id, version)``: re-ingesting
        the same triple replaces the existing document and its chunks.
        """
        result = await self.db.execute(
            select(MethodologyDocument).where(
                MethodologyDocument.registry == registry,
                MethodologyDocument.methodology_id == methodology_id,
                MethodologyDocument.version == version,
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            document = MethodologyDocument(
                registry=registry,
                methodology_id=methodology_id,
                title=title,
                version=version,
            )
            self.db.add(document)
        document.title = title
        document.source_url = source_url
        document.content = content
        document.metadata_ = metadata or {}
        await self.db.flush()

        await self.db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
        )

        texts = chunk_text(content)
        vectors = await self.embedder.embed(texts) if texts else []
        for index, (text, vector) in enumerate(zip(texts, vectors)):
            self.db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=text,
                    embedding=[float(v) for v in vector],
                    token_count=len(text.split()),
                )
            )
        await self.db.commit()
        await self.db.refresh(document)
        logger.info(
            "knowledge_document_ingested",
            document_id=str(document.id),
            registry=registry,
            methodology_id=methodology_id,
            version=version,
            chunks=len(texts),
        )
        return document

    async def search(
        self,
        query: str,
        registry: Optional[str] = None,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Vector-search chunks; returns ``[{chunk, document, score}]`` best-first."""
        stmt = select(KnowledgeChunk, MethodologyDocument).join(
            MethodologyDocument, KnowledgeChunk.document_id == MethodologyDocument.id
        )
        if registry:
            stmt = stmt.where(MethodologyDocument.registry == registry)
        result = await self.db.execute(stmt)
        rows = result.all()
        if not rows:
            return []

        query_vec = (await self.embedder.embed([query]))[0]
        ranked = top_k(query_vec, [row[0].embedding for row in rows], k)
        return [
            {
                "chunk": _chunk_to_dict(rows[i][0]),
                "document": _document_to_dict(rows[i][1]),
                "score": round(score, 6),
            }
            for i, score in ranked
        ]

    async def query_knowledge_base(
        self,
        question: str,
        registry: Optional[str] = None,
        k: int = 4,
    ) -> Dict[str, Any]:
        """RAG answer over retrieved methodology passages.

        Retrieves the top-k chunks, asks the Kimi LLM to synthesize a cited
        answer (citations are methodology IDs), and gracefully degrades to the
        top passages verbatim with an ``"unreviewed": True`` flag when the LLM
        is unavailable (no API key / error).
        """
        results = await self.search(question, registry=registry, k=k)
        passages = [
            {
                "methodology_id": r["document"]["methodology_id"],
                "title": r["document"]["title"],
                "version": r["document"]["version"],
                "registry": r["document"]["registry"],
                "chunk_index": r["chunk"]["chunk_index"],
                "content": r["chunk"]["content"],
                "score": r["score"],
            }
            for r in results
        ]
        base: Dict[str, Any] = {
            "question": question,
            "registry": registry,
            "passages": passages,
            "citations": [],
            "unreviewed": True,
            "answer": None,
        }
        if not passages:
            base["answer"] = "No methodology documents match this question."
            return base

        try:
            from app.services.kimi_api import get_kimi_client

            llm_result = await get_kimi_client().reason(
                prompt=(
                    "Answer the question using ONLY the retrieved methodology "
                    "passages below. Cite the methodology_id for every claim. "
                    "If the passages do not cover the question, say so explicitly."
                ),
                context={"question": question, "passages": passages},
                response_schema=RAG_ANSWER_SCHEMA,
            )
        except Exception as exc:  # noqa: BLE001 — LLM failure degrades to passages
            logger.warning("knowledge_rag_llm_failed", error=str(exc))
            return base

        if not isinstance(llm_result, dict) or llm_result.get("_fallback"):
            # Graceful fallback: passages returned verbatim, flagged unreviewed.
            return base

        citations = llm_result.get("citations")
        base["citations"] = [str(c) for c in citations] if isinstance(citations, list) else []
        base["answer"] = str(llm_result.get("answer") or "").strip() or None
        base["unreviewed"] = not base["answer"]
        return base

    async def delete_document(self, document_id: Any) -> bool:
        """Delete a document (cascades to chunks). Returns True when found."""
        from uuid import UUID

        doc_id = document_id if isinstance(document_id, UUID) else UUID(str(document_id))
        result = await self.db.execute(
            select(MethodologyDocument).where(MethodologyDocument.id == doc_id)
        )
        document = result.scalar_one_or_none()
        if document is None:
            return False
        await self.db.delete(document)
        await self.db.commit()
        return True

    async def list_documents(self, registry: Optional[str] = None) -> List[Dict[str, Any]]:
        """List ingested documents (newest first) with their chunk counts."""
        stmt = (
            select(MethodologyDocument, KnowledgeChunk.id)
            .outerjoin(KnowledgeChunk, KnowledgeChunk.document_id == MethodologyDocument.id)
            .order_by(MethodologyDocument.ingested_at.desc())
        )
        if registry:
            stmt = stmt.where(MethodologyDocument.registry == registry)
        result = await self.db.execute(stmt)
        counts: Dict[Any, int] = {}
        ordered: List[MethodologyDocument] = []
        seen = set()
        for doc, chunk_id in result.all():
            if doc.id not in seen:
                seen.add(doc.id)
                ordered.append(doc)
                counts[doc.id] = 0
            if chunk_id is not None:
                counts[doc.id] += 1
        return [{**_document_to_dict(doc), "chunk_count": counts[doc.id]} for doc in ordered]

    async def get_document(self, document_id: Any) -> Optional[Dict[str, Any]]:
        """Fetch a single document with its chunks."""
        from uuid import UUID

        doc_id = document_id if isinstance(document_id, UUID) else UUID(str(document_id))
        result = await self.db.execute(
            select(MethodologyDocument).where(MethodologyDocument.id == doc_id)
        )
        document = result.scalar_one_or_none()
        if document is None:
            return None
        chunks = await self.db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document.id)
            .order_by(KnowledgeChunk.chunk_index)
        )
        chunk_rows = chunks.scalars().all()
        return {
            **_document_to_dict(document),
            "content": document.content,
            "chunk_count": len(chunk_rows),
            "chunks": [_chunk_to_dict(c) for c in chunk_rows],
        }
