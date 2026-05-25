# Security Audit Guide

This document provides a checklist and automated scanner configuration for conducting security audits of CarbonVerify. Use this for internal reviews, penetration test preparation, and SOC2 evidence collection.

---

## Pre-Audit Preparation

### 1. Environment Setup

```bash
# Deploy a staging environment identical to production
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d

# Or deploy to a dedicated K8s namespace
kubectl create namespace carbonverify-audit
kubectl apply -k infrastructure/k8s/overlays/staging/
```

### 2. Create Audit Test Account

```bash
curl -X POST https://staging.carbonverify.io/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "security-audit@carbonverify.io",
    "password": "AuditPass123!",
    "name": "Security Audit",
    "role": "admin"
  }'
```

---

## Automated Scanning

### OWASP ZAP Baseline Scan

```bash
# Run ZAP baseline scan against staging
docker run -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py \
  -t https://staging.carbonverify.io \
  -r zap-report.html \
  -w zap-report.md
```

**Expected pass criteria:**
- No High or Critical alerts
- Medium alerts ≤ 3 (documented and accepted)

### Semgrep SAST

```bash
# Install semgrep
pip install semgrep

# Run on backend
semgrep --config=auto backend/app/ --json -o semgrep-backend.json

# Run on frontend
semgrep --config=auto frontend/src/ --json -o semgrep-frontend.json
```

**Critical rules to enable:**
- `python.flask.security` (adapted for FastAPI)
- `python.sqlalchemy.security`
- `javascript.react.security`
- `generic.secrets`

### Bandit (Python security linter)

```bash
pip install bandit
bandit -r backend/app/ -f json -o bandit-report.json
```

### npm audit (Frontend dependencies)

```bash
cd frontend
npm audit --audit-level=moderate
```

### Safety (Python dependency vulnerabilities)

```bash
pip install safety
safety check -r backend/requirements.txt --json -o safety-report.json
```

---

## Manual Audit Checklist

### Authentication & Authorization

| # | Check | Tool/Method | Pass Criteria |
|---|-------|-------------|---------------|
| 1 | Brute force protection | Burp Suite Intruder | Account locks after 5 failed attempts |
| 2 | JWT secret strength | `jwt_tool.py` | HS256 with ≥32 byte random key |
| 3 | Refresh token storage | Browser DevTools | Token in httpOnly cookie, NOT localStorage |
| 4 | Password complexity | Manual test | Rejects passwords <8 chars, no uppercase, no special char |
| 5 | Session timeout | Wait 30 min + test | Auto-logout after inactivity |
| 6 | RBAC enforcement | API calls as viewer | Viewer cannot access admin endpoints (403) |
| 7 | WebSocket auth | wscat without token | Connection rejected with code 1008 |
| 8 | API key auth on IoT | curl without X-API-Key | Returns 401 |

### Input Validation & Injection

| # | Check | Tool/Method | Pass Criteria |
|---|-------|-------------|---------------|
| 9 | SQL injection | `' OR 1=1 --` in search | No error, parameterized query |
| 10 | XSS in uploads | Upload HTML file with `<script>` | File rejected or sanitized |
| 11 | Path traversal | `../../../etc/passwd` filename | Sanitized to safe filename |
| 12 | Command injection | `; cat /etc/passwd` in params | No shell execution |
| 13 | NoSQL injection | JSON payload manipulation | Proper schema validation |
| 14 | File type validation | Rename .exe to .csv | Detected by magic bytes, rejected |

### Data Protection

| # | Check | Tool/Method | Pass Criteria |
|---|-------|-------------|---------------|
| 15 | PII encryption | DB query on users table | email/phone encrypted at rest |
| 16 | HTTPS enforcement | `curl -I http://...` | Redirects to HTTPS |
| 17 | HSTS header | `curl -I https://...` | `strict-transport-security` present |
| 18 | CSP header | `curl -I https://...` | `content-security-policy` present |
| 19 | Sensitive data in logs | Check app logs | No passwords, tokens, or PII in plaintext |
| 20 | GDPR erasure | Trigger DSR workflow | User data anonymized within 30 days |

### Infrastructure

| # | Check | Tool/Method | Pass Criteria |
|---|-------|-------------|---------------|
| 21 | Container security | `docker scan` or Trivy | No CRITICAL OS/package CVEs |
| 22 | Secret exposure | `git-secrets` or `trufflehog` | No secrets in git history |
| 23 | Rate limiting | `ab -n 1000 -c 10` | 429 responses after threshold |
| 24 | DB backup encryption | Check S3 bucket | Backups encrypted at rest (SSE-S3 or KMS) |
| 25 | Network policies | `kubectl get networkpolicies` | Default deny, explicit allow |

### Business Logic

| # | Check | Tool/Method | Pass Criteria |
|---|-------|-------------|---------------|
| 26 | IDOR (Insecure Direct Object Reference) | Access `/projects/{other-user-id}` | 403 forbidden |
| 27 | Mass assignment | POST with extra fields | Extra fields ignored by Pydantic |
| 28 | Race condition | Simultaneous credit purchases | Atomic DB transactions, no double-spend |
| 29 | Tokenization integrity | Fractionalize + verify sums | Math checks prevent overflow/underflow |

---

## Reporting Template

Create `security-audit-report-YYYY-MM-DD.md`:

```markdown
# Security Audit Report — CarbonVerify
**Date:** 2024-XX-XX
**Auditor:** [Name]
**Scope:** Full stack (API, frontend, infrastructure)
**Environment:** Staging

## Executive Summary
- Critical: 0
- High: 0
- Medium: 2
- Low: 3
- Info: 5

## Findings

### [MEDIUM-1] Title
**Description:** ...
**Impact:** ...
**Remediation:** ...
**Status:** Open / Accepted / Fixed

## Automated Scan Results
- ZAP: [zap-report.html](zap-report.html)
- Semgrep: [semgrep-backend.json](semgrep-backend.json)
- Bandit: [bandit-report.json](bandit-report.json)
- npm audit: [npm-audit.txt](npm-audit.txt)
```

---

## Remediation SLA

| Severity | Fix Timeline | Exception Process |
|----------|-------------|-------------------|
| Critical | 24 hours | CISO approval required |
| High | 72 hours | Security team lead approval |
| Medium | 14 days | Documented risk acceptance |
| Low | 30 days | Product owner approval |
