"""Validation workflow state machine with transition rules and guards."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple

from app.validation_engine.models import WorkflowRunStatus


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class TransitionGuardError(Exception):
    """Raised when a transition guard condition is not met."""
    pass


@dataclass(frozen=True)
class TransitionRule:
    """Defines a valid state transition."""
    from_state: WorkflowRunStatus
    to_state: WorkflowRunStatus
    # List of allowed actor types that can trigger this transition
    allowed_actors: Tuple[str, ...] = ("system", "user", "synthetic_actor", "remediation_engine")
    # Whether this transition requires a reason
    requires_reason: bool = False


# Define all valid transitions
VALID_TRANSITIONS: List[TransitionRule] = [
    # Start
    TransitionRule(WorkflowRunStatus.pending, WorkflowRunStatus.queued),
    TransitionRule(WorkflowRunStatus.queued, WorkflowRunStatus.running),

    # Normal flow
    TransitionRule(WorkflowRunStatus.running, WorkflowRunStatus.step_validating),
    TransitionRule(WorkflowRunStatus.step_validating, WorkflowRunStatus.proof_generating),
    TransitionRule(WorkflowRunStatus.proof_generating, WorkflowRunStatus.remediation_checking),
    TransitionRule(WorkflowRunStatus.remediation_checking, WorkflowRunStatus.step_validating),
    TransitionRule(WorkflowRunStatus.remediation_checking, WorkflowRunStatus.completed),

    # Failure paths
    TransitionRule(WorkflowRunStatus.step_validating, WorkflowRunStatus.failed),
    TransitionRule(WorkflowRunStatus.proof_generating, WorkflowRunStatus.failed),
    TransitionRule(WorkflowRunStatus.remediation_checking, WorkflowRunStatus.failed),
    TransitionRule(WorkflowRunStatus.running, WorkflowRunStatus.failed),

    # Remediation can bring us back to running
    TransitionRule(WorkflowRunStatus.failed, WorkflowRunStatus.running,
                   allowed_actors=("remediation_engine", "user")),
    TransitionRule(WorkflowRunStatus.failed, WorkflowRunStatus.queued,
                   allowed_actors=("remediation_engine", "user")),

    # Human intervention (users can drive the same transitions as system)
    # These are covered by the default allowed_actors above

    # Archival (terminal)
    TransitionRule(WorkflowRunStatus.completed, WorkflowRunStatus.archived),
    TransitionRule(WorkflowRunStatus.failed, WorkflowRunStatus.archived),

    # Direct transitions for testing/emergency/cancellation
    TransitionRule(WorkflowRunStatus.pending, WorkflowRunStatus.running,
                   allowed_actors=("user",)),
    TransitionRule(WorkflowRunStatus.pending, WorkflowRunStatus.failed,
                   allowed_actors=("user",)),
    TransitionRule(WorkflowRunStatus.queued, WorkflowRunStatus.failed),
]

# Build lookup tables for fast validation
_TRANSITION_MAP: Dict[Tuple[str, str], TransitionRule] = {
    (t.from_state.value, t.to_state.value): t for t in VALID_TRANSITIONS
}

# Valid target states from each state
_VALID_TARGETS: Dict[str, Set[str]] = {}
for t in VALID_TRANSITIONS:
    _VALID_TARGETS.setdefault(t.from_state.value, set()).add(t.to_state.value)


class WorkflowStateMachine:
    """State machine for validation workflow runs.

    Enforces valid transitions, actor permissions, and guard conditions.
    """

    def __init__(self):
        self._guards: Dict[Tuple[str, str], List[Callable]] = {}

    def add_guard(
        self,
        from_state: WorkflowRunStatus,
        to_state: WorkflowRunStatus,
        guard: Callable[[], bool],
    ) -> None:
        """Add a guard condition for a specific transition."""
        key = (from_state.value, to_state.value)
        self._guards.setdefault(key, []).append(guard)

    def can_transition(
        self,
        current: WorkflowRunStatus,
        target: WorkflowRunStatus,
        actor_type: str = "system",
    ) -> Tuple[bool, Optional[str]]:
        """Check if a transition is valid without executing it.

        Returns (is_valid, error_message).
        """
        key = (current.value, target.value)
        rule = _TRANSITION_MAP.get(key)
        if rule is None:
            return False, f"Invalid transition from '{current.value}' to '{target.value}'"

        if actor_type not in rule.allowed_actors:
            return (
                False,
                f"Actor type '{actor_type}' not allowed for transition "
                f"'{current.value}' -> '{target.value}'",
            )

        # Run guards
        guards = self._guards.get(key, [])
        for guard in guards:
            try:
                if not guard():
                    return False, f"Guard condition failed for transition '{current.value}' -> '{target.value}'"
            except Exception as exc:
                return False, f"Guard exception: {exc}"

        return True, None

    def transition(
        self,
        current: WorkflowRunStatus,
        target: WorkflowRunStatus,
        actor_type: str = "system",
    ) -> WorkflowRunStatus:
        """Execute a state transition, raising on invalid transitions."""
        is_valid, error = self.can_transition(current, target, actor_type)
        if not is_valid:
            raise TransitionError(error or "Unknown transition error")
        return target

    def get_valid_targets(self, current: WorkflowRunStatus) -> List[WorkflowRunStatus]:
        """Get all valid target states from the current state."""
        targets = _VALID_TARGETS.get(current.value, set())
        return [WorkflowRunStatus(t) for t in targets]

    def is_terminal(self, state: WorkflowRunStatus) -> bool:
        """Check if a state is terminal (no outgoing transitions)."""
        return len(_VALID_TARGETS.get(state.value, set())) == 0
