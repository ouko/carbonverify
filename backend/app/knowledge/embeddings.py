"""Embedding providers for the methodology knowledge base.

Two implementations behind a common ``Embedder`` protocol:

- ``LocalHashEmbedder`` — deterministic, dependency-free bag-of-hashed-n-grams
  vectors. Each whitespace token (and each adjacent token bigram) is hashed
  with SHA-256 into one of ``dim`` buckets; bucket counts are L2-normalized.
  This is a lexical approximation, NOT a semantic embedding: it captures
  term-overlap similarity well enough to rank obviously relevant chunks and
  works fully offline (tests, air-gapped deploys). It must not be treated as
  interchangeable with a trained embedding model for subtle paraphrase
  retrieval.
- ``OpenAICompatibleEmbedder`` — async httpx client for any
  OpenAI-compatible ``/embeddings`` endpoint, configured via
  ``KNOWLEDGE_EMBEDDER_URL`` / ``KNOWLEDGE_EMBEDDER_MODEL`` /
  ``KNOWLEDGE_EMBEDDER_API_KEY``.

``top_k`` is a pure-python cosine-similarity ranker shared by both.
"""

import hashlib
import math
import re
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    """Async text→vector provider."""

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of texts into equal-length float vectors."""
        ...


class LocalHashEmbedder:
    """Deterministic hashed n-gram count vectorizer (see module docstring)."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _bucketize(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = _TOKEN_RE.findall(text.lower())
        features = list(tokens)
        features.extend(f"{a}__{b}" for a, b in zip(tokens, tokens[1:]))
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).hexdigest()
            vec[int(digest[:8], 16) % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._bucketize(t) for t in texts]


class OpenAICompatibleEmbedder:
    """Async embedder against an OpenAI-compatible ``/embeddings`` endpoint."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.KNOWLEDGE_EMBEDDER_URL).rstrip("/")
        self.model = model or settings.KNOWLEDGE_EMBEDDER_MODEL or "text-embedding-3-small"
        self.api_key = api_key if api_key is not None else settings.KNOWLEDGE_EMBEDDER_API_KEY
        if not self.base_url:
            raise ValueError("OpenAICompatibleEmbedder requires a base URL")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not self.api_key:
            raise RuntimeError("KNOWLEDGE_EMBEDDER_API_KEY is not configured")
        response = await self._client.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "input": list(texts)},
        )
        response.raise_for_status()
        data = response.json()
        ordered: Dict[int, List[float]] = {}
        for item in data.get("data", []):
            ordered[int(item["index"])] = [float(v) for v in item["embedding"]]
        return [ordered[i] for i in sorted(ordered)]

    async def aclose(self) -> None:
        await self._client.aclose()


def get_embedder() -> Embedder:
    """Factory: remote embedder when configured, otherwise the local hash embedder."""
    settings = get_settings()
    if settings.KNOWLEDGE_EMBEDDER_URL and settings.KNOWLEDGE_EMBEDDER_API_KEY:
        try:
            return OpenAICompatibleEmbedder()
        except Exception as exc:  # noqa: BLE001 — degrade to local, never break ingest
            logger.warning("knowledge_embedder_fallback", error=str(exc))
    return LocalHashEmbedder()


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Pure-python cosine similarity (vectors are expected L2-normalized)."""
    dot = 0.0
    for x, y in zip(a, b):
        dot += x * y
    return dot


def top_k(
    query_vec: Sequence[float],
    candidates: Sequence[Sequence[float]],
    k: int,
) -> List[Tuple[int, float]]:
    """Rank candidate vectors against ``query_vec`` by cosine similarity.

    Returns up to ``k`` ``(index, score)`` pairs, best first. Pure python so
    it works on any backend without numpy.
    """
    scored = [(i, cosine_similarity(query_vec, c)) for i, c in enumerate(candidates)]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[: max(0, k)]


def embedding_dim(embedding: Sequence[float]) -> int:
    """Dimensionality helper kept for embedder introspection/logging."""
    return len(embedding)


__all__ = [
    "Embedder",
    "LocalHashEmbedder",
    "OpenAICompatibleEmbedder",
    "cosine_similarity",
    "embedding_dim",
    "get_embedder",
    "top_k",
]
