"""Core ValidationOrchestrator — drives workflow execution through the state machine."""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.validation_engine.models import (
    EscalationLevel,
    EscalationStatus,
    HumanEscalation,
    RemediationStatus,
    StepExecutionStatus,
    ValidationRemediation,
    ValidationRun,
    ValidationRunTransition,
    ValidationStepExecution,
    WorkflowRunStatus,
)
from app.validation_engine.schemas import WorkflowGraph, WorkflowStep
from app.validation_engine.state_machine import WorkflowStateMachine
from app.validation_engine.proofs import ProofGenerator
from app.validation_engine.synthetic import SyntheticActorFactory
from app.validation_engine.executors import StepExecutorRegistry
from app.validation_engine.remediation import RemediationEngine
from app.database import AsyncSessionLocal


def _canonical_json(data: Any) -> str:
    """Canonical JSON representation for hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _hash_transition(
    run_id: str,
    from_state: str,
    to_state: str,
    actor_type: str,
    occurred_at: datetime,
    previous_hash: Optional[str],
    metadata: Dict[str, Any],
) -> str:
    """Compute SHA-256 hash of a transition record for chain integrity."""
    payload = {
        "run_id": str(run_id),
        "from_state": from_state,
        "to_state": to_state,
        "actor_type": actor_type,
        "occurred_at": occurred_at.isoformat(),
        "previous_hash": previous_hash or "",
        "metadata": _canonical_json(metadata),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


class ValidationOrchestrator:
    """Orchestrates the execution of validation workflows.

    Manages state transitions, step execution, proof generation, remediation,
    and human escalation within a single workflow run.
    """

    def __init__(
        self,
        db: AsyncSession,
        proof_generator: Optional[ProofGenerator] = None,
        actor_factory: Optional[SyntheticActorFactory] = None,
        executor_registry: Optional[StepExecutorRegistry] = None,
        remediation_engine: Optional[RemediationEngine] = None,
    ):
        self.db = db
        self.state_machine = WorkflowStateMachine()
        self.proof_generator = proof_generator or ProofGenerator()
        self.actor_factory = actor_factory or SyntheticActorFactory()
        self.executor_registry = executor_registry or StepExecutorRegistry()
        self.remediation_engine = remediation_engine or RemediationEngine()
        self._run_cache: Dict[str, ValidationRun] = {}

    async def create_run(
        self,
        workflow_id: str,
        trigger_event: str,
        input_data: Dict[str, Any],
        project_id: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> ValidationRun:
        """Create a new validation run in PENDING state."""
        run = ValidationRun(
            workflow_id=uuid.UUID(workflow_id),
            project_id=uuid.UUID(project_id) if project_id else None,
            triggered_by=uuid.UUID(triggered_by) if triggered_by else None,
            trigger_event=trigger_event,
            input_data=input_data,
            status=WorkflowRunStatus.pending,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        self._run_cache[str(run.id)] = run
        return run

    async def advance_state(
        self,
        run: ValidationRun,
        target: WorkflowRunStatus,
        actor_type: str = "system",
        reason: Optional[str] = None,
        synthetic_actor_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationRunTransition:
        """Advance a run to a new state with full audit trail."""
        # Re-fetch run with row-level lock to prevent concurrent state mutations
        locked_result = await self.db.execute(
            select(ValidationRun).where(ValidationRun.id == run.id).with_for_update()
        )
        run = locked_result.scalar_one()

        current = run.status

        # Validate transition
        self.state_machine.transition(current, target, actor_type)

        # Update run state
        run.status = target
        if target == WorkflowRunStatus.running and run.started_at is None:
            run.started_at = datetime.now(timezone.utc)
        if target in (WorkflowRunStatus.completed, WorkflowRunStatus.failed):
            run.completed_at = datetime.now(timezone.utc)
        if target == WorkflowRunStatus.archived:
            run.archived_at = datetime.now(timezone.utc)

        # Get previous hash for chain
        prev = await self.db.execute(
            select(ValidationRunTransition)
            .where(ValidationRunTransition.run_id == run.id)
            .order_by(ValidationRunTransition.occurred_at.desc())
            .limit(1)
        )
        prev_transition = prev.scalar_one_or_none()
        previous_hash = prev_transition.transition_hash if prev_transition else None

        occurred_at = datetime.now(timezone.utc)
        transition_hash = _hash_transition(
            str(run.id),
            current.value,
            target.value,
            actor_type,
            occurred_at,
            previous_hash,
            metadata or {},
        )

        transition = ValidationRunTransition(
            run_id=run.id,
            from_state=current.value,
            to_state=target.value,
            triggered_by=run.triggered_by,
            actor_type=actor_type,
            synthetic_actor_id=uuid.UUID(synthetic_actor_id) if synthetic_actor_id else None,
            reason=reason,
            transition_hash=transition_hash,
            previous_hash=previous_hash,
            occurred_at=occurred_at,
            metadata_json=metadata or {},
        )
        self.db.add(transition)
        await self.db.commit()
        return transition

    async def execute_workflow(self, run_id: str) -> ValidationRun:
        """Execute a complete workflow run from PENDING through to completion."""
        result = await self.db.execute(
            select(ValidationRun).where(ValidationRun.id == uuid.UUID(run_id))
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise ValueError(f"Run {run_id} not found")

        # Load workflow graph
        from app.validation_engine.models import ValidationWorkflow
        wf_result = await self.db.execute(
            select(ValidationWorkflow).where(ValidationWorkflow.id == run.workflow_id)
        )
        workflow = wf_result.scalar_one()
        graph = WorkflowGraph.model_validate(workflow.workflow_graph)

        # Build step lookup
        steps_by_id: Dict[str, WorkflowStep] = {s.id: s for s in graph.steps}
        steps_in_order: List[WorkflowStep] = []

        # Topological sort (DAG validation)
        visited: set = set()
        temp_mark: set = set()

        def visit(step_id: str):
            if step_id in temp_mark:
                raise ValueError(f"Workflow cycle detected at step '{step_id}'")
            if step_id in visited:
                return
            temp_mark.add(step_id)
            step = steps_by_id.get(step_id)
            if step:
                for nxt in step.next_on_success:
                    if nxt in steps_by_id:
                        visit(nxt)
            temp_mark.remove(step_id)
            visited.add(step_id)
            steps_in_order.append(steps_by_id[step_id])

        visit(graph.entry_step)
        # Add any disconnected steps at the end (they won't execute but are validated)
        for s in graph.steps:
            if s.id not in visited:
                steps_in_order.append(s)

        # Advance to queued
        await self.advance_state(run, WorkflowRunStatus.queued, reason="Run initialized")
        # Advance to running
        await self.advance_state(run, WorkflowRunStatus.running, reason="Starting workflow execution")

        # Execute steps
        context = {
            "input": run.input_data,
            "variables": graph.variables.copy(),
            "outputs": {},
        }

        executed_step_ids: set = set()
        step_index_map: Dict[str, int] = {s.id: i for i, s in enumerate(steps_in_order)}

        try:
            current_step_id = graph.entry_step
            while current_step_id and current_step_id in steps_by_id:
                if current_step_id in executed_step_ids:
                    break  # Prevent infinite loops
                executed_step_ids.add(current_step_id)

                step = steps_by_id[current_step_id]
                if not step.enabled:
                    # Skip disabled steps
                    current_step_id = step.next_on_success[0] if step.next_on_success else None
                    continue

                step_exec = await self._execute_step(run, step, step_index_map[step.id], context)

                if step_exec.status == StepExecutionStatus.success:
                    # Decide next step
                    next_ids = step.next_on_success
                    if len(next_ids) == 1:
                        current_step_id = next_ids[0] if next_ids[0] != "end" else None
                    elif len(next_ids) > 1:
                        # Branching: take first for now (advanced branching via decision gates)
                        current_step_id = next_ids[0] if next_ids[0] != "end" else None
                    else:
                        current_step_id = None
                else:
                    # Step failed — attempt remediation
                    remediated = await self._handle_step_failure(run, step_exec, step, context)
                    if remediated:
                        # Retry the same step
                        executed_step_ids.discard(current_step_id)
                        continue
                    else:
                        # Follow failure path
                        next_ids = step.next_on_failure
                        if next_ids and next_ids[0] != "fail":
                            current_step_id = next_ids[0]
                        else:
                            raise RuntimeError(
                                f"Step '{step.id}' failed and no remediation or fallback path succeeded"
                            )

            # Persist final outputs and complete the run
            run.output_data = context["outputs"]
            await self.db.commit()
            await self._generate_final_proofs(run)
            await self.advance_state(run, WorkflowRunStatus.completed, reason="All steps executed successfully")

        except Exception as exc:
            run.error_message = str(exc)
            await self.db.commit()
            await self.advance_state(
                run, WorkflowRunStatus.failed, reason=f"Workflow execution failed: {exc}"
            )
            # Attempt run-level remediation
            await self._handle_run_failure(run, str(exc))

        return run

    async def _execute_step(
        self,
        run: ValidationRun,
        step: WorkflowStep,
        step_index: int,
        context: Dict[str, Any],
    ) -> ValidationStepExecution:
        """Execute a single workflow step."""
        await self.advance_state(run, WorkflowRunStatus.step_validating, reason=f"Entering step '{step.id}'")

        step_exec = ValidationStepExecution(
            run_id=run.id,
            step_id=step.id,
            step_index=step_index,
            step_type=step.type,
            step_name=step.name,
            status=StepExecutionStatus.running,
            input_payload={"context_keys": list(context.keys()), "step_config": step.config},
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(step_exec)
        await self.db.commit()
        await self.db.refresh(step_exec)

        try:
            # Resolve config with variable interpolation
            resolved_config = self._resolve_variables(step.config, context)

            # Get executor
            executor = self.executor_registry.get_executor(step.type)

            # Execute
            started = datetime.now(timezone.utc)
            output = await executor.execute(resolved_config, context, run)
            duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

            step_exec.output_payload = output
            step_exec.duration_ms = duration_ms
            step_exec.status = StepExecutionStatus.success
            step_exec.completed_at = datetime.now(timezone.utc)

            # Update context
            context["outputs"][step.id] = output

            # Compute step hash
            step_data = {
                "step_id": step.id,
                "input": step_exec.input_payload,
                "output": output,
                "duration_ms": duration_ms,
            }
            step_exec.step_hash = hashlib.sha256(
                _canonical_json(step_data).encode("utf-8")
            ).hexdigest()

        except Exception as exc:
            step_exec.status = StepExecutionStatus.failed
            step_exec.error_message = str(exc)
            step_exec.completed_at = datetime.now(timezone.utc)
            step_exec.retry_count += 1

        await self.db.commit()

        # Record step-level transition
        await self._record_step_transition(run, step_exec, step)

        # Generate proof for this step
        await self.advance_state(run, WorkflowRunStatus.proof_generating, reason=f"Generating proof for step '{step.id}'")
        if step.capture_proof:
            await self.proof_generator.capture_step_proof(self.db, run, step_exec, step)

        await self.advance_state(
            run, WorkflowRunStatus.remediation_checking, reason=f"Checking remediation for step '{step.id}'"
        )
        return step_exec

    async def _handle_step_failure(
        self,
        run: ValidationRun,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
        context: Dict[str, Any],
    ) -> bool:
        """Attempt to remediate a failed step. Returns True if remediated."""
        if run.remediation_count >= 3:
            return False

        action = self.remediation_engine.decide_action(step_exec, step)
        if action is None:
            return False

        run.remediation_count += 1
        remediation = ValidationRemediation(
            run_id=run.id,
            step_execution_id=step_exec.id,
            failure_condition=step_exec.error_message or "Unknown failure",
            action=action,
            action_params={"step_id": step.id, "retry_count": step_exec.retry_count},
            status=RemediationStatus.attempted,
        )
        self.db.add(remediation)
        await self.db.commit()

        try:
            result = await self.remediation_engine.execute(
                action, step_exec, step, context, self.db, run
            )
            remediation.status = RemediationStatus.succeeded
            remediation.result_json = result
            remediation.resolved_at = datetime.now(timezone.utc)
            await self.db.commit()

            # Reset step execution for retry
            step_exec.status = StepExecutionStatus.retried
            await self.db.commit()
            await self._record_step_transition(run, step_exec, step)
            return True

        except Exception as exc:
            remediation.status = RemediationStatus.failed
            remediation.error_message = str(exc)
            await self.db.commit()
            return False

    async def _handle_run_failure(self, run: ValidationRun, error_message: str) -> None:
        """Handle complete workflow run failure — escalate if needed."""
        # Check if human escalation is warranted
        severity = 0.7 if run.remediation_count >= 3 else 0.5
        level = EscalationLevel.l2_engineer if severity >= 0.7 else EscalationLevel.l1_operator

        escalation = HumanEscalation(
            run_id=run.id,
            escalation_reason=error_message,
            severity_score=severity,
            level=level,
            status=EscalationStatus.pending,
            context_json={
                "remediation_count": run.remediation_count,
                "run_input": run.input_data,
                "error": error_message,
            },
            sla_deadline=datetime.now(timezone.utc) + timedelta(hours=4),
        )
        self.db.add(escalation)
        run.human_intervened = True
        await self.db.commit()

    async def _generate_final_proofs(self, run: ValidationRun) -> None:
        """Generate the Merkle tree and anchor to Radix."""
        await self.proof_generator.build_merkle_tree(self.db, run)
        await self.proof_generator.anchor_to_radix(self.db, run)
        await self.db.commit()

    async def _record_step_transition(
        self,
        run: ValidationRun,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
    ) -> None:
        """Write a step-level transition record documenting the status change."""
        # Determine from_state based on current step_exec status
        to_state = step_exec.status.value
        from_state = StepExecutionStatus.running.value
        if to_state == StepExecutionStatus.retried.value:
            from_state = StepExecutionStatus.failed.value

        prev = await self.db.execute(
            select(ValidationRunTransition)
            .where(ValidationRunTransition.run_id == run.id)
            .order_by(ValidationRunTransition.occurred_at.desc())
            .limit(1)
        )
        prev_transition = prev.scalar_one_or_none()
        previous_hash = prev_transition.transition_hash if prev_transition else None

        occurred_at = datetime.now(timezone.utc)
        transition_hash = _hash_transition(
            str(run.id),
            from_state,
            to_state,
            "system",
            occurred_at,
            previous_hash,
            {"step_id": step.id, "step_name": step.name, "step_type": step.type.value},
        )

        transition = ValidationRunTransition(
            run_id=run.id,
            from_state=from_state,
            to_state=to_state,
            triggered_by=run.triggered_by,
            actor_type="system",
            reason=f"Step '{step.id}' transitioned from {from_state} to {to_state}",
            transition_hash=transition_hash,
            previous_hash=previous_hash,
            occurred_at=occurred_at,
            metadata_json={"step_id": step.id, "step_name": step.name, "step_type": step.type.value},
        )
        self.db.add(transition)
        await self.db.commit()

    def _resolve_variables(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Interpolate variables like ${input.x} or ${variables.y} in config values."""
        result = {}
        for key, value in config.items():
            result[key] = self._resolve_value(value, context)
        return result

    def _resolve_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """Recursively resolve variable references in a value."""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            path = value[2:-1].split(".")
            current = context
            for part in path:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return value  # Keep original if not found
            return current
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(item, context) for item in value]
        return value
