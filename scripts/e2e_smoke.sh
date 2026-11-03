#!/usr/bin/env bash
#
# e2e_smoke.sh — live-stack smoke test for CarbonVerify (NOT CI-blocking).
#
# Runs a minimal end-to-end check against a RUNNING backend:
#   health check → login with demo credentials → authenticated reads of the
#   Command Center surfaces (health score, escalations, audit decisions).
#
# Usage:
#   ./scripts/e2e_smoke.sh
#
# Environment:
#   BASE_URL        API base URL        (default: http://localhost:8000)
#   DEMO_EMAIL      demo account email  (required; e.g. operator@carbonverify.demo)
#   DEMO_PASSWORD   demo account password (required; e.g. DemoPass123!)
#
# The script is defensive: it never exits mid-check without a summary, treats
# any unexpected HTTP status as a failure for that check, and exits non-zero
# if any check fails or credentials are missing.
#
# Requires: curl, python3 (for JSON parsing; falls back to grep if absent).

set -u

BASE_URL="${BASE_URL:-http://localhost:8000}"
DEMO_EMAIL="${DEMO_EMAIL:-}"
DEMO_PASSWORD="${DEMO_PASSWORD:-}"

PASS=0
FAIL=0
CHECKS=()

log()  { printf '%s\n' "$*"; }
pass() { PASS=$((PASS + 1)); CHECKS+=("PASS  $1"); }
fail() { FAIL=$((FAIL + 1)); CHECKS+=("FAIL  $1 — $2"); }

# extract a string field from JSON on stdin; empty string if absent
json_field() {
    python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get("'"$1"'", "") or "")
except Exception:
    print("")'
}

# ─── Credential gate ─────────────────────────────────────────────────────────

if [ -z "$DEMO_EMAIL" ] || [ -z "$DEMO_PASSWORD" ]; then
    log "ERROR: DEMO_EMAIL and DEMO_PASSWORD must be set."
    log "Example:"
    log "  DEMO_EMAIL=operator@carbonverify.demo DEMO_PASSWORD=DemoPass123! $0"
    exit 2
fi

# ─── 1. Health check ─────────────────────────────────────────────────────────

HEALTH_BODY=$(curl -fsS --max-time 10 "$BASE_URL/health/" 2>/dev/null)
if [ $? -eq 0 ] && [ -n "$HEALTH_BODY" ]; then
    HEALTH_STATUS=$(printf '%s' "$HEALTH_BODY" | json_field status)
    if [ -n "$HEALTH_STATUS" ]; then
        pass "GET /health/ (status=$HEALTH_STATUS)"
    else
        pass "GET /health/ (reachable)"
    fi
else
    fail "GET /health/" "no response from $BASE_URL — is the stack running?"
fi

# ─── 2. Login (real auth flow) ───────────────────────────────────────────────

LOGIN_BODY=$(curl -fsS --max-time 10 -X POST "$BASE_URL/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\": $(python3 -c 'import json,os;print(json.dumps(os.environ["DEMO_EMAIL"]))'),
         \"password\": $(python3 -c 'import json,os;print(json.dumps(os.environ["DEMO_PASSWORD"]))')}" 2>/dev/null)

TOKEN=$(printf '%s' "$LOGIN_BODY" | json_field access_token)
if [ -n "$TOKEN" ]; then
    pass "POST /auth/login (token obtained)"
else
    MFA=$(printf '%s' "$LOGIN_BODY" | json_field mfa_required)
    if [ "$MFA" = "True" ] || [ "$MFA" = "true" ]; then
        fail "POST /auth/login" "demo account has MFA enabled; smoke test cannot complete MFA"
    else
        fail "POST /auth/login" "invalid credentials or unexpected response"
    fi
fi

AUTH_HEADER="Authorization: Bearer $TOKEN"

# ─── 3. Authenticated reads ──────────────────────────────────────────────────

check_get() {
    # $1 = path, $2 = label
    if [ -z "$TOKEN" ]; then
        fail "GET $1" "skipped (no token)"
        return
    fi
    BODY=$(curl -fsS --max-time 10 "$BASE_URL$1" -H "$AUTH_HEADER" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$BODY" ]; then
        pass "GET $1"
    else
        fail "GET $1" "HTTP error or empty body"
    fi
}

check_get "/api/v1/escalations/health/score"      "health score"
check_get "/api/v1/escalations/"                  "escalations list"
check_get "/api/v1/audit/decisions"               "audit decisions"
check_get "/api/v1/remediation/stats"             "remediation stats"
check_get "/api/v1/validation/health"             "validation health"

# ─── Summary ─────────────────────────────────────────────────────────────────

log ""
log "── Smoke summary ($BASE_URL) ──"
for line in "${CHECKS[@]}"; do
    log "  $line"
done
log ""
log "Result: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
