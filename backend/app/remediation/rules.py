"""Remediation strategy library and default rule seeding.

Each strategy receives a :class:`RuleContext` describing the failing target and
returns an :class:`AttemptVerdict`. Strategies never raise for expected
failure shapes — they return ``success=False`` with an explanatory ``error``
so the engine can persist a ``failed`` attempt row and keep going.
"""

import importlib
import inspect
import random
import statistics
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.logging import get_logger
from app.models import HumanReviewQueue, QueueItemTypeEnum, QueueStatusEnum
from app.remediation.models import RemediationRule

logger = get_logger(__name__)

# Strategy names (stored on remediation_rules.strategy).
STRATEGY_AUTO_CORRECT = "auto_correct"
STRATEGY_BACKOFF_RETRY = "backoff_retry"
STRATEGY_JITTER_RETRY = "jitter_retry"
STRATEGY_CONSERVATIVE_FALLBACK = "conservative_fallback"
STRATEGY_INTERPOLATE_OR_EXCLUDE = "interpolate_or_exclude"
STRATEGY_KB_DRAFT_RESPONSE = "kb_draft_response"

Sleeper = Callable[[float], Awaitable[None]]
# Optional per-attempt executors injected by callers (Phase 4 failure-injection
# tests use these to exercise the retry strategies against real operations).
AttemptFn = Callable[["RuleContext"], Any]
DraftFn = Callable[..., Any]


@dataclass
class RuleContext:
    """Everything a strategy needs for one attempt."""

    db: AsyncSession
    rule: RemediationRule
    target_type: str
    target_id: str
    project_id: Optional[uuid.UUID]
    failing_state: Dict[str, Any]
    attempt_number: int
    sleeper: Sleeper
    attempt_fn: Optional[AttemptFn] = None
    draft_fn: Optional[DraftFn] = None


@dataclass
class AttemptVerdict:
    """Result of one strategy attempt."""

    success: bool
    state: Optional[Dict[str, Any]] = None  # replacement state; None = unchanged
    detail: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    # True when the attempt should stop the round without counting as a
    # failure (e.g. circuit breaker open → queue-for-retry).
    deferred: bool = False


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _target_uuid(target_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(target_id)
    except (ValueError, AttributeError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_URL, f"carbonverify:remediation:{target_id}")


async def _retry_success(ctx: RuleContext) -> Optional[bool]:
    """Resolve whether a retry attempt succeeds.

    Priority: injected ``attempt_fn`` > explicit ``retry_outcome`` signal in
    the failing state (bool or per-attempt list) > None (no signal).
    """
    if ctx.attempt_fn is not None:
        try:
            return bool(await _maybe_await(ctx.attempt_fn(ctx)))
        except Exception as exc:  # noqa: BLE001 — a failing executor is a failed attempt
            logger.warning("remediation_attempt_fn_error", error=str(exc))
            return False
    outcome = ctx.failing_state.get("retry_outcome")
    if isinstance(outcome, list):
        idx = min(ctx.attempt_number - 1, len(outcome) - 1)
        return bool(outcome[idx]) if outcome else None
    if outcome is not None:
        return bool(outcome)
    return None


# ─── a. form_validation_error → auto_correct ──────────────────────────────────

async def strategy_auto_correct(ctx: RuleContext) -> AttemptVerdict:
    """Apply schema defaults for fields that failed validation."""
    form = ctx.failing_state.get("form")
    if not isinstance(form, dict):
        return AttemptVerdict(False, error="failing_state has no 'form' dict to correct")

    raw_errors = ctx.failing_state.get("errors", {})
    if isinstance(raw_errors, dict):
        error_fields = list(raw_errors.keys())
    elif isinstance(raw_errors, list):
        error_fields = [str(e).split(":", 1)[0].strip() for e in raw_errors]
    else:
        error_fields = []

    defaults: Dict[str, Any] = {}
    if isinstance(ctx.rule.config.get("defaults"), dict):
        defaults.update(ctx.rule.config["defaults"])
    if isinstance(ctx.failing_state.get("defaults"), dict):
        defaults.update(ctx.failing_state["defaults"])

    corrected = dict(form)
    corrections: Dict[str, Dict[str, Any]] = {}
    for field_name in error_fields:
        if field_name in defaults and field_name in corrected:
            corrections[field_name] = {
                "from": corrected[field_name],
                "to": defaults[field_name],
            }
            corrected[field_name] = defaults[field_name]

    if not corrections:
        return AttemptVerdict(
            False,
            detail={"error_fields": error_fields, "available_defaults": sorted(defaults)},
            error="no failing field has a default to apply",
        )
    return AttemptVerdict(
        True,
        state={"form": corrected, "corrections": corrections},
        detail={"corrections": corrections},
    )


# ─── b. api_timeout_rate_limit → backoff_retry ────────────────────────────────

async def strategy_backoff_retry(ctx: RuleContext) -> AttemptVerdict:
    """Exponential backoff with jitter; defers to queue-for-retry when the
    circuit breaker for the failing service is open."""
    service = ctx.failing_state.get("service")
    breaker = CIRCUIT_BREAKERS.get(str(service)) if service else None
    if breaker is not None and breaker.is_open:
        return AttemptVerdict(
            False,
            deferred=True,
            detail={"service": service, "reason": "circuit_breaker_open", "queued_for_retry": True},
            error=f"circuit breaker open for service '{service}'",
        )

    base = float(ctx.rule.config.get("base_delay_seconds", 1.0))
    factor = float(ctx.rule.config.get("backoff_factor", 2.0))
    cap = float(ctx.rule.config.get("max_delay_seconds", 30.0))
    delay = min(cap, base * (factor ** (ctx.attempt_number - 1)))
    jitter = random.uniform(0.0, delay * 0.1)
    await ctx.sleeper(delay + jitter)

    success = await _retry_success(ctx)
    detail = {
        "service": service,
        "delay_seconds": round(delay, 4),
        "jitter_seconds": round(jitter, 4),
        "attempt_signal": success,
    }
    if success is None:
        return AttemptVerdict(
            False,
            deferred=True,
            detail={**detail, "queued_for_retry": True},
            error="no retry outcome signal available — queued for caller retry",
        )
    if success:
        return AttemptVerdict(True, state=dict(ctx.failing_state), detail=detail)
    return AttemptVerdict(False, detail=detail, error="retry did not resolve the failure")


# ─── c. db_deadlock → jitter_retry ────────────────────────────────────────────

async def strategy_jitter_retry(ctx: RuleContext) -> AttemptVerdict:
    """Immediate retry with small random jitter (deadlocks usually clear)."""
    max_jitter = float(ctx.rule.config.get("max_jitter_seconds", 0.5))
    jitter = random.uniform(0.0, max_jitter)
    await ctx.sleeper(jitter)

    success = await _retry_success(ctx)
    detail = {"jitter_seconds": round(jitter, 4), "attempt_signal": success}
    if success is None:
        return AttemptVerdict(
            False,
            deferred=True,
            detail={**detail, "queued_for_retry": True},
            error="no retry outcome signal available — queued for caller retry",
        )
    if success:
        return AttemptVerdict(True, state=dict(ctx.failing_state), detail=detail)
    return AttemptVerdict(False, detail=detail, error="deadlock retry did not resolve the failure")


# ─── d. calculation_anomaly → conservative_fallback ───────────────────────────

async def strategy_conservative_fallback(ctx: RuleContext) -> AttemptVerdict:
    """Replace an anomalous calculation value with its conservative lower
    bound and flag the substitution for human review (priority 3)."""
    report = ctx.failing_state.get("anomaly_report")
    if not isinstance(report, dict):
        return AttemptVerdict(False, error="failing_state has no 'anomaly_report' dict")

    field_name = str(report.get("field") or "value")
    fallback = ctx.failing_state.get("conservative_value", report.get("lower_bound"))
    if fallback is None:
        return AttemptVerdict(
            False,
            detail={"anomaly_report": report},
            error="no conservative fallback value (lower_bound) available",
        )

    state = {
        "field": field_name,
        "original_value": report.get("value"),
        "fallback_value": fallback,
        "provenance": "conservative_fallback",
        "flagged_for_review": True,
    }
    reason = (
        f"Conservative fallback applied to anomalous '{field_name}': "
        f"{report.get('value')} → {fallback}. Please confirm the substitution."
    )
    review_item = HumanReviewQueue(
        item_type=QueueItemTypeEnum.calculation,
        item_id=_target_uuid(ctx.target_id),
        reason=reason,
        priority=3,
        status=QueueStatusEnum.pending,
        context_json={
            "project_id": str(ctx.project_id) if ctx.project_id else None,
            "target_type": ctx.target_type,
            "target_id": ctx.target_id,
            "rule_key": ctx.rule.rule_key,
            "anomaly_report": report,
            "fallback_state": state,
        },
    )
    ctx.db.add(review_item)
    await ctx.db.flush()

    return AttemptVerdict(
        True,
        state=state,
        detail={"review_flagged": True, "review_item_id": str(review_item.id), "reason": reason},
    )


# ─── e. missing_data_gap → interpolate_or_exclude ─────────────────────────────

def _missing_runs(series: List[Any]) -> List[List[int]]:
    runs: List[List[int]] = []
    for idx, value in enumerate(series):
        if value is None:
            if runs and runs[-1][-1] == idx - 1:
                runs[-1].append(idx)
            else:
                runs.append([idx])
    return runs


async def strategy_interpolate_or_exclude(ctx: RuleContext) -> AttemptVerdict:
    """Linearly interpolate small, stable gaps; otherwise exclude the missing
    points with a written justification."""
    series = ctx.failing_state.get("series")
    if not isinstance(series, list) or not series:
        return AttemptVerdict(False, error="failing_state has no 'series' list")

    max_gap = int(ctx.rule.config.get("max_gap", 2))
    min_observed = int(ctx.rule.config.get("min_observed", 5))
    max_cv = float(ctx.rule.config.get("max_cv", 0.5))

    runs = _missing_runs(series)
    if not runs:
        return AttemptVerdict(False, error="series contains no missing points")

    observed = [v for v in series if v is not None]
    n = len(observed)
    mean = statistics.fmean(observed)
    std = statistics.pstdev(observed) if n > 1 else 0.0
    cv = (std / abs(mean)) if mean else (0.0 if std == 0 else float("inf"))

    longest = max(len(r) for r in runs)
    edge_gap = runs[0][0] == 0 or runs[-1][-1] == len(series) - 1

    if longest > max_gap:
        justification = (
            f"gap of {longest} consecutive missing points exceeds the maximum of "
            f"{max_gap} for interpolation — excluded rather than fabricating data"
        )
    elif n < min_observed:
        justification = (
            f"only {n} observed points (< {min_observed}) — linear interpolation is "
            f"statistically unsupported; missing points excluded"
        )
    elif cv > max_cv:
        justification = (
            f"series variance unstable (CV={cv:.2f} > {max_cv:.2f}) — interpolation "
            f"could amplify noise; missing points excluded"
        )
    elif edge_gap:
        justification = (
            "gap at the series edge has no bounding observation on one side — linear "
            "interpolation impossible; missing points excluded"
        )
    else:
        filled = list(series)
        interpolated: List[int] = []
        for run in runs:
            left = filled[run[0] - 1]
            right = filled[run[-1] + 1]
            steps = len(run) + 1
            for offset, idx in enumerate(run, start=1):
                filled[idx] = left + (right - left) * (offset / steps)
                interpolated.append(idx)
        return AttemptVerdict(
            True,
            state={
                "series": filled,
                "provenance": {
                    "method": "linear_interpolation",
                    "source": "remediation",
                    "interpolated_indices": interpolated,
                },
            },
            detail={
                "decision": "interpolated",
                "interpolated_indices": interpolated,
                "observed_points": n,
                "cv": round(cv, 4),
            },
        )

    excluded = [idx for run in runs for idx in run]
    kept = [v for v in series if v is not None]
    return AttemptVerdict(
        True,
        state={
            "series": kept,
            "provenance": {
                "method": "exclusion",
                "source": "remediation",
                "excluded_indices": excluded,
                "justification": justification,
            },
        },
        detail={"decision": "excluded", "excluded_indices": excluded, "justification": justification},
    )


# ─── f. vvb_clarification → kb_draft_response ─────────────────────────────────

async def strategy_kb_draft_response(ctx: RuleContext) -> AttemptVerdict:
    """Draft a VVB clarification response from the knowledge base (Phase 5)
    or the Kimi API; resolved when a non-empty draft is produced."""
    query_text = str(ctx.failing_state.get("query_text") or "")
    if not query_text.strip():
        return AttemptVerdict(False, error="failing_state has no 'query_text'")
    project_data = ctx.failing_state.get("project_data") or {}
    methodology_kb: Optional[str] = ctx.failing_state.get("methodology_kb")

    draft: Optional[str] = None
    kb_used: Optional[str] = None

    if ctx.draft_fn is not None:
        try:
            draft = await _maybe_await(ctx.draft_fn(ctx))
            kb_used = "injected_draft_fn"
        except Exception as exc:  # noqa: BLE001 — a failing drafter is a failed attempt
            return AttemptVerdict(False, error=f"draft function failed: {exc}")
    else:
        # Prefer the Phase 5 knowledge base when present.
        try:
            kb_module = importlib.import_module("app.knowledge")
            query_fn = None
            for attr in ("query_knowledge_base", "search_knowledge", "query"):
                candidate = getattr(kb_module, attr, None)
                if callable(candidate):
                    query_fn = candidate
                    break
            if query_fn is None and hasattr(kb_module, "service"):
                service = getattr(kb_module, "service")
                for attr in ("query", "search", "query_knowledge_base"):
                    candidate = getattr(service, attr, None)
                    if callable(candidate):
                        query_fn = candidate
                        break
            if query_fn is not None:
                kb_result = await _maybe_await(query_fn(query_text))
                if isinstance(kb_result, (list, tuple)):
                    draft = "\n\n".join(str(item) for item in kb_result if item)
                elif kb_result is not None:
                    draft = str(kb_result)
                kb_used = "knowledge_base"
        except ImportError:
            logger.debug("knowledge_base_unavailable", detail="falling back to Kimi API")

        if not draft:
            try:
                from app.services.kimi_api import get_kimi_client

                draft = await get_kimi_client().draft_vvb_response(
                    query_text, project_data, methodology_kb
                )
                kb_used = "kimi_api"
            except Exception as exc:  # noqa: BLE001 — network/auth failures degrade to failed attempt
                return AttemptVerdict(False, error=f"kimi draft failed: {exc}")

    if not draft or not str(draft).strip():
        return AttemptVerdict(
            False,
            detail={"kb_source": kb_used},
            error="no draft content produced",
        )

    return AttemptVerdict(
        True,
        state={"draft_response": str(draft), "provenance": kb_used},
        detail={"kb_source": kb_used, "draft_length": len(str(draft))},
    )


STRATEGIES: Dict[str, Callable[[RuleContext], Awaitable[AttemptVerdict]]] = {
    STRATEGY_AUTO_CORRECT: strategy_auto_correct,
    STRATEGY_BACKOFF_RETRY: strategy_backoff_retry,
    STRATEGY_JITTER_RETRY: strategy_jitter_retry,
    STRATEGY_CONSERVATIVE_FALLBACK: strategy_conservative_fallback,
    STRATEGY_INTERPOLATE_OR_EXCLUDE: strategy_interpolate_or_exclude,
    STRATEGY_KB_DRAFT_RESPONSE: strategy_kb_draft_response,
}

DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "rule_key": "form_validation_error",
        "category": "form_validation_error",
        "description": "Apply schema defaults to fields that failed form validation.",
        "strategy": STRATEGY_AUTO_CORRECT,
        "config": {},
    },
    {
        "rule_key": "api_timeout_rate_limit",
        "category": "api_timeout_rate_limit",
        "description": "Retry API calls with exponential backoff + jitter; defer to queue when the circuit breaker is open.",
        "strategy": STRATEGY_BACKOFF_RETRY,
        "config": {"base_delay_seconds": 1.0, "backoff_factor": 2.0, "max_delay_seconds": 30.0},
    },
    {
        "rule_key": "db_deadlock",
        "category": "db_deadlock",
        "description": "Immediately retry database operations deadlocked with small random jitter.",
        "strategy": STRATEGY_JITTER_RETRY,
        "config": {"max_jitter_seconds": 0.5},
    },
    {
        "rule_key": "calculation_anomaly",
        "category": "calculation_anomaly",
        "description": "Substitute the conservative lower-bound estimate for anomalous calculations and flag for human review.",
        "strategy": STRATEGY_CONSERVATIVE_FALLBACK,
        "config": {},
    },
    {
        "rule_key": "missing_data_gap",
        "category": "missing_data_gap",
        "description": "Linearly interpolate small stable gaps; otherwise exclude missing points with justification.",
        "strategy": STRATEGY_INTERPOLATE_OR_EXCLUDE,
        "config": {"max_gap": 2, "min_observed": 5, "max_cv": 0.5},
    },
    {
        "rule_key": "vvb_clarification",
        "category": "vvb_clarification",
        "description": "Draft a response to a VVB clarification query from the knowledge base or Kimi API.",
        "strategy": STRATEGY_KB_DRAFT_RESPONSE,
        "config": {},
    },
]


async def seed_default_rules(db: AsyncSession) -> List[RemediationRule]:
    """Insert the default rule set, skipping rule_keys that already exist.

    Existing rows are left untouched so operator edits (config, enabled) are
    never clobbered by a re-seed. Returns all rule rows for the default keys.
    """
    result = await db.execute(
        select(RemediationRule).where(
            RemediationRule.rule_key.in_([r["rule_key"] for r in DEFAULT_RULES])
        )
    )
    existing = {rule.rule_key: rule for rule in result.scalars().all()}

    for spec in DEFAULT_RULES:
        if spec["rule_key"] not in existing:
            rule = RemediationRule(
                rule_key=spec["rule_key"],
                category=spec["category"],
                description=spec["description"],
                strategy=spec["strategy"],
                config=dict(spec["config"]),
                enabled=True,
            )
            db.add(rule)
            existing[spec["rule_key"]] = rule

    await db.commit()
    return list(existing.values())
