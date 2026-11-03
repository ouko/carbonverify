"""Base agent class for Kimi Claw multi-agent orchestration."""

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Confidence blending weighting: heuristic engines anchor the score, the LLM
# review moderates it. Documented in every blended reasoning string.
HEURISTIC_WEIGHT = 0.4
LLM_WEIGHT = 0.6
BLEND_FORMULA = f"heuristic*{HEURISTIC_WEIGHT} + llm*{LLM_WEIGHT}"


class AgentResult:
    """Standard result format for all agent executions.

    ``reasoning`` is a human-readable explanation of how the result was
    reached (suitable for the audit trail); ``evidence`` is a dict of the key
    facts cited. Both flow into orchestrator decision records and review-queue
    context when present.
    """

    def __init__(
        self,
        status: str,  # "completed" | "failed" | "queued_for_review"
        confidence_score: float,
        output_data: dict[str, Any],
        errors: list | None = None,
        execution_time_ms: int | None = None,
        reasoning: str | None = None,
        evidence: dict[str, Any] | None = None,
    ):
        self.status = status
        self.confidence_score = max(0.0, min(1.0, confidence_score))
        self.output_data = output_data
        self.errors = errors or []
        self.execution_time_ms = execution_time_ms
        self.reasoning = reasoning
        self.evidence = evidence or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "confidence_score": self.confidence_score,
            "output_data": self.output_data,
            "errors": self.errors,
            "execution_time_ms": self.execution_time_ms,
            "reasoning": self.reasoning,
            "evidence": self.evidence,
        }


class BaseAgent(ABC):
    """Abstract base class for all Kimi Claw agents."""

    agent_type: str = "base"

    def __init__(self, project_id: uuid.UUID, db_session=None):
        self.project_id = project_id
        self.db = db_session
        self.logger = get_logger(f"agent.{self.agent_type}")

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> AgentResult:
        """Execute the agent's core logic.

        Args:
            context: Shared context dictionary with project state, previous agent outputs, etc.

        Returns:
            AgentResult with status, confidence score, and output data.
        """
        raise NotImplementedError

    # ─── Shared LLM-reasoning helpers ─────────────────────────────────────

    @property
    def kimi(self):
        """Lazily-initialized shared Kimi API client."""
        client = getattr(self, "_kimi_client", None)
        if client is None:
            from app.services.kimi_api import get_kimi_client

            client = get_kimi_client()
            self._kimi_client = client
        return client

    async def reason_with_llm(
        self,
        task_prompt: str,
        context: dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a structured LLM reasoning task, always returning a dict.

        Falls back to ``{"_fallback": True, ...}`` when the Kimi API is
        unavailable or errors, so agent logic never blocks on the network.
        """
        try:
            return await self.kimi.reason(
                prompt=task_prompt,
                context=context,
                tools=tools,
                response_schema=response_schema,
            )
        except Exception as exc:
            self.logger.warning(
                "llm_reasoning_failed",
                agent_type=self.agent_type,
                error=str(exc),
            )
            return {"_fallback": True, "error": str(exc)}

    def blend_confidence(self, heuristic: float, llm: float | None = None) -> float:
        """Blend heuristic engine confidence with an LLM review score.

        Weighting: heuristic * 0.4 + llm * 0.6 when an LLM score is present,
        otherwise the heuristic stands alone. Callers should document the
        ``BLEND_FORMULA`` weighting in their reasoning string.
        """
        heuristic = max(0.0, min(1.0, heuristic))
        if llm is None:
            return heuristic
        llm = max(0.0, min(1.0, llm))
        return max(0.0, min(1.0, heuristic * HEURISTIC_WEIGHT + llm * LLM_WEIGHT))

    @staticmethod
    def build_output(
        reasoning: str,
        evidence: dict[str, Any],
        **data: Any,
    ) -> dict[str, Any]:
        """Build output_data with mandatory audit-trail fields."""
        return {**data, "reasoning": reasoning, "evidence": evidence}

    def _no_data_result(self, reasoning: str, evidence: dict[str, Any] | None = None) -> AgentResult:
        """Standard graceful result for projects with no data yet (0.5-0.7 confidence)."""
        return AgentResult(
            status="completed",
            confidence_score=0.6,
            output_data=self.build_output(reasoning, evidence or {}),
            reasoning=reasoning,
            evidence=evidence or {},
        )

    async def execute(self, trigger_event: str, context: dict[str, Any]) -> AgentResult:
        """Wrapper that records timing and logs execution."""
        start = time.perf_counter()
        self.logger.info(
            "agent_start",
            agent_type=self.agent_type,
            project_id=str(self.project_id),
            trigger=trigger_event,
        )

        try:
            result = await self.run(context)
        except Exception as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            self.logger.error(
                "agent_error",
                agent_type=self.agent_type,
                project_id=str(self.project_id),
                error=str(exc),
                elapsed_ms=elapsed,
            )
            return AgentResult(
                status="failed",
                confidence_score=0.0,
                output_data={},
                errors=[str(exc)],
                execution_time_ms=elapsed,
            )

        elapsed = int((time.perf_counter() - start) * 1000)
        result.execution_time_ms = elapsed

        self.logger.info(
            "agent_complete",
            agent_type=self.agent_type,
            project_id=str(self.project_id),
            status=result.status,
            confidence=result.confidence_score,
            elapsed_ms=elapsed,
        )
        return result

    def _compute_confidence_tier(self, score: float) -> str:
        """Categorize confidence score into action tiers."""
        if score >= 0.95:
            return "auto_advance"
        elif score >= 0.85:
            return "human_review"
        else:
            return "escalate"
