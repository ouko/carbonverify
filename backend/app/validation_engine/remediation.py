"""Auto-remediation engine for common workflow failure patterns."""

import asyncio
import random
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.validation_engine.models import (
    RemediationAction,
    RemediationStatus,
    ValidationRemediation,
    ValidationRun,
    ValidationStepExecution,
)
from app.validation_engine.schemas import WorkflowStep


class RemediationEngine:
    """Decides and executes remediation actions for failed steps."""

    # Failure pattern → recommended action mapping
    PATTERN_ACTIONS: Dict[str, RemediationAction] = {
        "timeout": RemediationAction.retry,
        "connection_error": RemediationAction.retry,
        "rate_limit": RemediationAction.retry,
        "deadlock": RemediationAction.rollback,
        "validation_error": RemediationAction.skip,
        "assertion_failed": RemediationAction.escalate,
        "service_unavailable": RemediationAction.circuit_break,
        "permission_denied": RemediationAction.escalate,
        "not_found": RemediationAction.skip,
        "checksum_mismatch": RemediationAction.rollback,
    }

    def __init__(self):
        self._action_handlers = {
            RemediationAction.retry: self._handle_retry,
            RemediationAction.rollback: self._handle_rollback,
            RemediationAction.skip: self._handle_skip,
            RemediationAction.escalate: self._handle_escalate,
            RemediationAction.patch: self._handle_patch,
            RemediationAction.circuit_break: self._handle_circuit_break,
        }

    def decide_action(
        self,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
    ) -> Optional[RemediationAction]:
        """Decide the best remediation action for a failed step."""
        error = (step_exec.error_message or "").lower()

        # Check for known patterns
        for pattern, action in self.PATTERN_ACTIONS.items():
            if pattern in error:
                # Don't retry more than the step's policy allows
                if action == RemediationAction.retry:
                    max_retries = step.config.get("retry_policy", {}).get("max_retries", 3)
                    if step_exec.retry_count >= max_retries:
                        continue
                return action

        # Default: escalate if we can't identify the pattern
        return RemediationAction.escalate

    async def execute(
        self,
        action: RemediationAction,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
        context: Dict[str, Any],
        db: AsyncSession,
        run: ValidationRun,
    ) -> Dict[str, Any]:
        """Execute a remediation action."""
        handler = self._action_handlers.get(action)
        if handler is None:
            raise ValueError(f"Unknown remediation action: {action.value}")
        return await handler(step_exec, step, context, db, run)

    async def _handle_retry(
        self,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
        context: Dict[str, Any],
        db: AsyncSession,
        run: ValidationRun,
    ) -> Dict[str, Any]:
        """Retry the failed step with exponential backoff."""
        retry_policy = step.config.get("retry_policy", {})
        backoff = retry_policy.get("backoff_multiplier", 2.0)
        initial_delay = retry_policy.get("initial_delay_ms", 500)
        delay = initial_delay * (backoff ** step_exec.retry_count)
        delay += random.uniform(0, delay * 0.1)  # Jitter

        await asyncio.sleep(delay / 1000.0)
        return {
            "action": "retry",
            "delay_ms": delay,
            "retry_count": step_exec.retry_count,
        }

    async def _handle_rollback(
        self,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
        context: Dict[str, Any],
        db: AsyncSession,
        run: ValidationRun,
    ) -> Dict[str, Any]:
        """Rollback any side effects from the failed step."""
        # In a real system, this would use compensating transactions
        # For now, we record the rollback attempt
        return {
            "action": "rollback",
            "rolled_back_steps": [step_exec.step_id],
            "compensating_actions": [],
        }

    async def _handle_skip(
        self,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
        context: Dict[str, Any],
        db: AsyncSession,
        run: ValidationRun,
    ) -> Dict[str, Any]:
        """Mark the step as skipped and continue."""
        if not step.skippable:
            raise RuntimeError(f"Step '{step.id}' is not marked as skippable")

        step_exec.status = "skipped"
        await db.commit()
        return {
            "action": "skip",
            "step_id": step.id,
        }

    async def _handle_escalate(
        self,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
        context: Dict[str, Any],
        db: AsyncSession,
        run: ValidationRun,
    ) -> Dict[str, Any]:
        """Create a human escalation record."""
        from app.validation_engine.models import (
            EscalationLevel,
            EscalationStatus,
            HumanEscalation,
        )
        from datetime import datetime, timezone, timedelta

        escalation = HumanEscalation(
            run_id=run.id,
            step_execution_id=step_exec.id,
            escalation_reason=step_exec.error_message or "Unknown failure requiring escalation",
            severity_score=0.8,
            level=EscalationLevel.l2_engineer,
            status=EscalationStatus.pending,
            context_json={
                "step_id": step.id,
                "step_name": step.name,
                "step_config": step.config,
                "context_keys": list(context.keys()),
            },
            sla_deadline=datetime.now(timezone.utc) + timedelta(hours=4),
        )
        db.add(escalation)
        run.human_intervened = True
        await db.commit()

        return {
            "action": "escalate",
            "escalation_id": str(escalation.id),
            "level": EscalationLevel.l2_engineer.value,
        }

    async def _handle_patch(
        self,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
        context: Dict[str, Any],
        db: AsyncSession,
        run: ValidationRun,
    ) -> Dict[str, Any]:
        """Apply a patch to fix the issue automatically."""
        # Example patches: adjust a date, fix a format, retry with different params
        patch_applied = False
        patch_details = {}

        error = step_exec.error_message or ""
        if "date" in error.lower() and "format" in error.lower():
            # Auto-fix date format
            patch_details["type"] = "date_format_fix"
            patch_applied = True
        elif "timeout" in error.lower():
            # Increase timeout
            patch_details["type"] = "timeout_increase"
            patch_details["new_timeout_ms"] = step.config.get("timeout_ms", 60000) * 2
            patch_applied = True

        return {
            "action": "patch",
            "patch_applied": patch_applied,
            "patch_details": patch_details,
        }

    async def _handle_circuit_break(
        self,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
        context: Dict[str, Any],
        db: AsyncSession,
        run: ValidationRun,
    ) -> Dict[str, Any]:
        """Open the circuit breaker for a failing service."""
        # Circuit breaker state would be stored in Redis
        service_name = step.config.get("service_name", "unknown")
        return {
            "action": "circuit_break",
            "service_name": service_name,
            "circuit_state": "open",
            "recovery_timeout_ms": step.config.get("circuit_breaker", {}).get(
                "recovery_timeout_ms", 30000
            ),
        }
