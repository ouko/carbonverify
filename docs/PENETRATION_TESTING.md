# CarbonVerify Penetration Testing & Security Assurance

## Overview

CarbonVerify implements a defense-in-depth security strategy combining automated continuous scanning, quarterly third-party assessments, and a planned bug bounty program.

## Automated Security Testing (CI/CD)

### OWASP ZAP Integration

The GitHub Actions workflow `.github/workflows/security-scan.yml` runs on every push to `main`/`develop`, every PR, and weekly:

1. **Baseline Scan** — Passive scan against the running application to detect:
   - Missing security headers
   - Information disclosure
   - Insecure cookies
   - CSP misconfigurations

2. **API Scan** — Active scan against the OpenAPI spec to detect:
   - Injection vulnerabilities (SQLi, NoSQLi, XSS)
   - Broken authentication
   - Excessive data exposure
   - Broken access control

3. **Dependency Scanning** — `safety` checks Python packages for known CVEs

4. **Static Analysis** — `bandit` scans Python code for security anti-patterns

5. **Secret Detection** — `gitleaks` scans commit history for leaked credentials

### Running Locally

```bash
# Start the full stack
docker compose up -d

# Run ZAP baseline scan
docker run -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py \
  -t http://localhost:8000 \
  -r zap-report.html

# Run Bandit
cd backend && bandit -r app/

# Run Safety
cd backend && safety check -r requirements.txt
```

## Manual Penetration Testing

### Quarterly Third-Party Assessment

**Scope:**
- External infrastructure (API, web frontend, mobile backend)
- Authentication and authorization mechanisms
- Data protection at rest and in transit
- Blockchain anchoring integrity
- Compliance workflow security

**Deliverables:**
- Executive summary with risk ratings
- Detailed findings with reproduction steps
- Remediation roadmap with priorities
- Re-test validation report

### Test Cases

#### Authentication
- [ ] Brute-force protection activates after 5 failed attempts
- [ ] Account lockout persists for 30 minutes
- [ ] MFA TOTP codes are validated with 1-step window tolerance
- [ ] Refresh token rotation prevents replay attacks
- [ ] Session timeout after 30 minutes of inactivity

#### Authorization
- [ ] Developers cannot access other developers' projects
- [ ] Viewers cannot modify any data
- [ ] Operators cannot access admin-only functions
- [ ] GPS coordinates are masked based on role
- [ ] PDD drafting is blocked for all roles (independence)

#### Data Protection
- [ ] Sensitive fields (GPS, household IDs) are masked in API responses
- [ ] Audit logs capture all significant actions with hashes
- [ ] Radix DLT anchoring creates immutable verification trail
- [ ] Consent records are enforceable and auditable
- [ ] DSR workflows respect 30-day SLA

#### Blockchain Integrity
- [ ] Hash recomputation matches stored hash
- [ ] Radix transaction reference is retrievable
- [ ] Tampered data fails verification
- [ ] Manual anchor creates valid on-chain reference

## Bug Bounty Program (Year 2+)

**Planned Launch:** TBD (not yet launched)

**Scope:**
- API endpoints (`/api/v1/*`)
- Web application (`https://app.carbonverify.io`)
- Mobile field app
- WhatsApp bot webhook

**Out of Scope:**
- Social engineering
- Physical access attempts
- DoS/DDoS attacks
- Third-party dependencies (unless exploitable through our code)

**Rewards:**
- Critical: $2,500 + public acknowledgment
- High: $1,000
- Medium: $500
- Low: $100

**Reporting:** security@carbonverify.io with encrypted PGP key

## Security Contacts

- **Security Lead:** security@carbonverify.io
- **Incident Response:** incident@carbonverify.io

## Compliance Mapping

| Control | Implementation | Test |
|---------|---------------|------|
| Kenya DPA — Consent | `ConsentRecord` model | `test_record_and_get_consent` |
| Kenya DPA — DSR | `DataSubjectRequest` workflow | `test_submit_dsr` |
| Kenya DPA — Breach Notification | 72h SLA in `BreachNotification` | `test_report_breach` |
| VVB Independence | PDD drafting blocked | `test_independence_check_blocks_pdd` |
| Audit Trail | `AuditLog` + Radix anchoring | `test_anchor_audit_log_disabled` |
| Methodology Versioning | `MethodologyVersion` with approval | `test_create_and_list_methodology` |
