"""Base agent class for Kimi Claw multi-agent orchestration."""

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentResult:
    """Standard result format for all agent executions."""

    def __init__(
        self,
        status: str,  # "completed" | "failed" | "queued_for_review"
        confidence_score: float,
        output_data: Dict[str, Any],
        errors: Optional[list] = None,
        execution_time_ms: Optional[int] = None,
    ):
        self.status = status
        self.confidence_score = max(0.0, min(1.0, confidence_score))
        self.output_data = output_data
        self.errors = errors or []
        self.execution_time_ms = execution_time_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "confidence_score": self.confidence_score,
            "output_data": self.output_data,
            "errors": self.errors,
            "execution_time_ms": self.execution_time_ms,
        }


class BaseAgent(ABC):
    """Abstract base class for all Kimi Claw agents."""

    agent_type: str = "base"

    def __init__(self, project_id: uuid.UUID, db_session=None):
        self.project_id = project_id
        self.db = db_session
        self.logger = get_logger(f"agent.{self.agent_type}")

    @abstractmethod
    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Execute the agent's core logic.

        Args:
            context: Shared context dictionary with project state, previous agent outputs, etc.

        Returns:
            AgentResult with status, confidence score, and output data.
        """
        raise NotImplementedError

    async def execute(self, trigger_event: str, context: Dict[str, Any]) -> AgentResult:
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
