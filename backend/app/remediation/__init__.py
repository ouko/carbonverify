"""Shared self-healing remediation engine.

Applies deterministic recovery strategies (auto-correct, retry with
backoff/jitter, conservative fallback, interpolation/exclusion, KB-drafted
responses) to failing platform operations, records every attempt with
before/after state hashes, and escalates to the human review queue plus the
Merkle-chained agent-decision audit trail after repeated failures.
"""

from app.remediation.engine import RemediationEngine, RemediationOutcome
from app.remediation.models import RemediationAttempt, RemediationRule
from app.remediation.rules import DEFAULT_RULES, seed_default_rules

__all__ = [
    "DEFAULT_RULES",
    "RemediationAttempt",
    "RemediationEngine",
    "RemediationOutcome",
    "RemediationRule",
    "seed_default_rules",
]
