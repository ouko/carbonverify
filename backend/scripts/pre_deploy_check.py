#!/usr/bin/env python3
"""Pre-deploy gate for CarbonVerify.

Checks deployment readiness against a running API:

1. ``GET /api/v1/escalations/health/score`` — overall score must be >= 90.
2. ``GET /api/v1/validation/health`` — no 7-consecutive-day-below-90 streak in
   validation health snapshots, and every synthetic journey passed in the last
   24 hours (at least one completed run, zero failed runs per journey).

Usage:
    python scripts/pre_deploy_check.py [--base-url URL] [--token TOKEN]
    python scripts/pre_deploy_check.py --offline-selftest
    python scripts/pre_deploy_check.py --with-tests
    python scripts/pre_deploy_check.py --local   # (optional, not implemented)

Exit 0 = pass, exit 1 = block (reasons printed to stdout).

The scoring logic lives in importable functions (``evaluate_gate``) so CI can
self-test the checker without a server via ``--offline-selftest``.

``--with-tests`` runs the success-criteria acceptance suite (autonomous E2E,
remediation fault injection, operator scale) via pytest in a subprocess and
blocks the deploy when any of them fail.

Dependencies: standard library + httpx only (``--with-tests`` additionally
invokes the backend virtualenv's pytest).
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

SCORE_THRESHOLD = 90
STREAK_LIMIT = 7

DEFAULT_BASE_URL = "http://localhost:8000"
HEALTH_SCORE_PATH = "/api/v1/escalations/health/score"
VALIDATION_HEALTH_PATH = "/api/v1/validation/health"

BACKEND_ROOT = Path(__file__).resolve().parent.parent
ACCEPTANCE_TEST_FILES = [
    "tests/test_autonomous_e2e.py",
    "tests/test_remediation_injection.py",
    "tests/test_operator_scale.py",
]


def evaluate_gate(
    system_health: Optional[Dict[str, Any]],
    validation_health: Optional[Dict[str, Any]],
) -> List[str]:
    """Evaluate deploy-gate conditions. Returns a list of blocking reasons
    (empty list means pass). Pure function — no network, no I/O."""
    reasons: List[str] = []

    # 1. Overall system health score.
    score = (system_health or {}).get("score")
    if score is None:
        reasons.append("escalations health score is missing from the response")
    elif int(score) < SCORE_THRESHOLD:
        reasons.append(
            f"overall health score {score} is below the required {SCORE_THRESHOLD}"
        )

    # 2. Validation snapshots: 7-day below-threshold streak blocks deploys.
    latest = (validation_health or {}).get("latest")
    history = (validation_health or {}).get("history") or []
    if not latest and not history:
        reasons.append("no validation health snapshots recorded")
    else:
        streak = int((latest or {}).get("consecutive_below_threshold") or 0)
        if streak >= STREAK_LIMIT:
            reasons.append(
                f"validation health has been below {SCORE_THRESHOLD} for "
                f"{streak} consecutive snapshots (limit {STREAK_LIMIT})"
            )

    # 3. Synthetic journeys must all be passing in the last 24 hours.
    journeys = (validation_health or {}).get("journeys") or {}
    if not journeys:
        reasons.append("no synthetic journey runs recorded in the last 24 hours")
    else:
        for name in sorted(journeys):
            stats = journeys[name] or {}
            completed = int(stats.get("completed", 0))
            failed = int(stats.get("failed", 0))
            if failed > 0:
                reasons.append(
                    f"synthetic journey '{name}' had {failed} failed run(s) "
                    "in the last 24 hours"
                )
            if completed == 0:
                reasons.append(
                    f"synthetic journey '{name}' has no completed runs "
                    "in the last 24 hours"
                )

    return reasons


def fetch_json(
    client: httpx.Client, base_url: str, path: str, token: Optional[str]
) -> Dict[str, Any]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = client.get(f"{base_url.rstrip('/')}{path}", headers=headers, timeout=15.0)
    response.raise_for_status()
    return response.json()


def selftest() -> int:
    """Validate the checker's logic against stubbed data (no server needed)."""
    failures: List[str] = []

    journeys_pass = {
        "synthetic_developer_journey": {"completed": 3, "failed": 0},
        "synthetic_enumerator_journey": {"completed": 3, "failed": 0},
        "synthetic_calc_anomaly_recovery": {"completed": 3, "failed": 0},
    }
    passing = evaluate_gate(
        {"score": 95, "components": {}},
        {
            "latest": {"score": 95, "consecutive_below_threshold": 2},
            "history": [],
            "journeys": journeys_pass,
        },
    )
    if passing:
        failures.append(f"expected pass, got reasons: {passing}")

    low_score = evaluate_gate({"score": 82, "components": {}}, None)
    if not any("below the required" in r for r in low_score):
        failures.append("low overall score was not flagged")

    streak_blocked = evaluate_gate(
        {"score": 95, "components": {}},
        {
            "latest": {"score": 70, "consecutive_below_threshold": 7},
            "history": [],
            "journeys": journeys_pass,
        },
    )
    if not any("consecutive snapshots" in r for r in streak_blocked):
        failures.append("7-snapshot below-threshold streak was not flagged")

    failed_journey = {**journeys_pass, "synthetic_enumerator_journey": {"completed": 2, "failed": 1}}
    journey_blocked = evaluate_gate(
        {"score": 95, "components": {}},
        {"latest": None, "history": [], "journeys": failed_journey},
    )
    if not any("synthetic journey 'synthetic_enumerator_journey'" in r for r in journey_blocked):
        failures.append("failing synthetic journey was not flagged")

    no_runs = evaluate_gate(
        {"score": 95, "components": {}},
        {"latest": None, "history": [], "journeys": {}},
    )
    if not any("no synthetic journey runs" in r for r in no_runs):
        failures.append("missing journey runs were not flagged")

    if failures:
        for failure in failures:
            print(f"SELFTEST FAIL: {failure}")
        return 1
    print("pre_deploy_check selftest: all gate cases passed")
    return 0


def run_acceptance_tests() -> int:
    """Run the success-criteria acceptance suite; block on any failure."""
    python = os.environ.get("PYTHON", sys.executable)
    cmd = [python, "-m", "pytest", *ACCEPTANCE_TEST_FILES, "-q"]
    print(f"running acceptance tests: {' '.join(cmd)} (cwd={BACKEND_ROOT})")
    try:
        proc = subprocess.run(cmd, cwd=str(BACKEND_ROOT))
    except OSError as exc:
        print(f"BLOCK: could not launch pytest: {exc}")
        return 1
    if proc.returncode != 0:
        print(
            "BLOCK: success-criteria acceptance tests failed "
            f"(pytest exit {proc.returncode})"
        )
        return 1
    print("PASS: success-criteria acceptance tests green")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CarbonVerify pre-deploy gate")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DEPLOY_CHECK_BASE_URL", DEFAULT_BASE_URL),
        help=f"API base URL (default: {DEFAULT_BASE_URL} or DEPLOY_CHECK_BASE_URL)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("DEPLOY_CHECK_TOKEN"),
        help="Bearer token for authenticated health endpoints (or DEPLOY_CHECK_TOKEN)",
    )
    parser.add_argument(
        "--offline-selftest",
        action="store_true",
        help="validate the checker's logic against stubbed data without a server",
    )
    parser.add_argument(
        "--with-tests",
        action="store_true",
        help="run the success-criteria acceptance test suite and block on failure",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="also run an in-process synthetic journey (optional; not implemented)",
    )
    args = parser.parse_args(argv)

    if args.offline_selftest:
        return selftest()

    if args.with_tests:
        return run_acceptance_tests()

    if args.local:
        print(
            "note: --local in-process journey execution is not supported by this "
            "checker; use the validation engine's run_synthetic_validation task instead"
        )

    try:
        with httpx.Client() as client:
            system_health = fetch_json(client, args.base_url, HEALTH_SCORE_PATH, args.token)
            validation_health = fetch_json(
                client, args.base_url, VALIDATION_HEALTH_PATH, args.token
            )
    except httpx.HTTPStatusError as exc:
        print(f"BLOCK: health endpoint returned HTTP {exc.response.status_code}: {exc}")
        print("hint: health endpoints require an operator/admin bearer token (--token)")
        return 1
    except httpx.HTTPError as exc:
        print(f"BLOCK: could not reach {args.base_url}: {exc}")
        return 1

    reasons = evaluate_gate(system_health, validation_health)
    if reasons:
        print("BLOCK: deploy gate failed:")
        for reason in reasons:
            print(f"  - {reason}")
        return 1

    print(
        f"PASS: deploy gate green "
        f"(score={system_health.get('score')}, "
        f"snapshots={len((validation_health or {}).get('history') or [])})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
