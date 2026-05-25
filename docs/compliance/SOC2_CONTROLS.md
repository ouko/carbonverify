# SOC 2 Type II Controls Mapping

This document maps CarbonVerify's security controls to SOC 2 Trust Services Criteria (TSC). Use this as the foundation for SOC 2 Type II audit preparation.

---

## Trust Services Criteria Overview

| TSC | Description | Status |
|-----|-------------|--------|
| **CC1** | Control Environment | ✅ Documented |
| **CC2** | Communication & Information | ✅ Implemented |
| **CC3** | Risk Assessment | ✅ Documented |
| **CC4** | Monitoring Activities | ✅ Implemented |
| **CC5** | Control Activities | ✅ Implemented |
| **CC6** | Logical & Physical Access | ✅ Implemented |
| **CC7** | System Operations | ✅ Implemented |
| **CC8** | Change Management | ⚠️ Partial |
| **CC9** | Risk Mitigation | ✅ Documented |
| **A1** | Availability | ⚠️ Partial |
| **C1** | Confidentiality | ✅ Implemented |
| **PI1** | Processing Integrity | ⚠️ Partial |
| **P1** | Privacy | ✅ Implemented |

---

## CC1 — Control Environment

### CC1.1: Integrity & Ethical Values
| Control | Evidence | Owner |
|---------|----------|-------|
| Code of Conduct | `docs/compliance/CODE_OF_CONDUCT.md` | CEO |
| Security training | Annual security awareness training records | HR |
| Background checks | Background check policy for employees with DB access | HR |

### CC1.2: Board Independence
| Control | Evidence | Owner |
|---------|----------|-------|
| Security review meetings | Quarterly board security review minutes | CEO |

### CC1.3: Organizational Structure
| Control | Evidence | Owner |
|---------|----------|-------|
| RACI matrix | `docs/compliance/RACI_MATRIX.md` | CTO |
| Security roles defined | Security engineer, DPO roles in job descriptions | HR |

---

## CC2 — Communication & Information

### CC2.1: Internal Communication
| Control | Evidence | Owner |
|---------|----------|-------|
| Incident response plan | `docs/compliance/INCIDENT_RESPONSE.md` | Security |
| Security policies | `docs/compliance/POLICIES/` directory | Security |
| Change notifications | Slack #security-announcements channel | Security |

### CC2.2: External Communication
| Control | Evidence | Owner |
|---------|----------|-------|
| Privacy policy | `/compliance/privacy-policy` endpoint | Legal |
| Terms of Service | `/compliance/terms-of-service` endpoint | Legal |
| Breach notification | `BREACH_NOTIFICATION_SLA_HOURS=72` in config | Security |
| Status page | status.carbonverify.io (recommended) | SRE |

---

## CC3 — Risk Assessment

### CC3.1: Risk Identification
| Control | Evidence | Owner |
|---------|----------|-------|
| Annual risk assessment | `docs/compliance/RISK_ASSESSMENT_2024.md` | Security |
| Threat model | `docs/compliance/THREAT_MODEL.md` | Security |
| Dependency scan | `safety check` in CI/CD | Security |

### CC3.2: Fraud Risk
| Control | Evidence | Owner |
|---------|----------|-------|
| Separation of duties | RBAC: admin/operator/viewer roles | Security |
| Transaction audit log | `audit_logs` table in DB | Security |

### CC3.3: Change Risk
| Control | Evidence | Owner |
|---------|----------|-------|
| Change advisory board | CAB meeting notes for production changes | SRE |
| Staging environment | `infrastructure/k8s/overlays/staging/` | SRE |

### CC3.4 — Risk Mitigation
| Control | Evidence | Owner |
|---------|----------|-------|
| Risk register | `docs/compliance/RISK_REGISTER.md` | Security |
| Penetration tests | Annual third-party pentest reports | Security |
| Vulnerability management | Trivy/Snyk scans in CI/CD | Security |

---

## CC4 — Monitoring Activities

### CC4.1: Ongoing Monitoring
| Control | Evidence | Owner |
|---------|----------|-------|
| Prometheus metrics | `/metrics` endpoint | SRE |
| Alertmanager rules | `infrastructure/k8s/base/monitoring/` | SRE |
| Log aggregation | Structured JSON logs to stdout → Fluentd/CloudWatch | SRE |
| Uptime monitoring | External pingdom/Datadog Synthetics | SRE |

### CC4.2: Evaluation & Remediation
| Control | Evidence | Owner |
|---------|----------|-------|
| Quarterly access reviews | `docs/compliance/ACCESS_REVIEWS/` | Security |
| Vulnerability remediation SLA | `docs/SECURITY_AUDIT.md` remediation table | Security |
| Incident post-mortems | `docs/compliance/INCIDENTS/` | SRE |

---

## CC5 — Control Activities

### CC5.1: Control Selection & Development
| Control | Evidence | Owner |
|---------|----------|-------|
| Authentication controls | JWT + httpOnly cookies + MFA + rate limiting | Security |
| Authorization controls | RBAC middleware | Security |
| Input validation | Pydantic schemas + magic bytes detection | Security |
| Encryption | TLS 1.3 + field-level Fernet for PII | Security |

### CC5.2: Control Technology
| Control | Evidence | Owner |
|---------|----------|-------|
| Automated CI/CD checks | `.github/workflows/ci.yml` | SRE |
| Infrastructure as Code | K8s manifests in Git | SRE |
| Secret management | AWS Secrets Manager / Vault (recommended) | SRE |

### CC5.3: Control Policies
| Control | Evidence | Owner |
|---------|----------|-------|
| Password policy | 8+ chars, uppercase, digit, special char | Security |
| Access deprovisioning | Offboarding checklist | HR |
| Data retention | `DATA_RETENTION_YEARS_RAW_PHOTOS=7` | Legal |

---

## CC6 — Logical & Physical Access

### CC6.1: Logical Access Security
| Control | Evidence | Owner |
|---------|----------|-------|
| User authentication | JWT access (15min) + refresh (7 days) | Security |
| Multi-factor authentication | TOTP via `pyotp` for admin/operator | Security |
| Account lockout | 5 failed attempts → 15 min lockout | Security |
| Session management | Redis-backed sessions with TTL | Security |
| API key auth | `X-API-Key` for IoT webhooks | Security |

### CC6.2: Privileged Access
| Control | Evidence | Owner |
|---------|----------|-------|
| Role-based access control | `admin`, `operator`, `viewer` roles | Security |
| Principle of least privilege | `require_viewer` / `require_operator` / `require_admin` | Security |
| Privileged access logging | Admin actions logged to `audit_logs` | Security |

### CC6.3: Access Removal
| Control | Evidence | Owner |
|---------|----------|-------|
| Automated deprovisioning | Celery task to purge terminated user data | Security |
| GDPR erasure | `process_erasure_request` Celery task | Legal |

### CC6.4: Physical Access
| Control | Evidence | Owner |
|---------|----------|-------|
| Cloud infrastructure | AWS/GCP data center physical security | Cloud Provider |
| Office access | Badge access to office (if applicable) | Facilities |

---

## CC7 — System Operations

### CC7.1: System Monitoring
| Control | Evidence | Owner |
|---------|----------|-------|
| Health checks | `/health` endpoint + K8s liveness/readiness | SRE |
| Performance monitoring | Prometheus + Grafana dashboards | SRE |
| Error tracking | Sentry integration (recommended) | SRE |

### CC7.2: Incident Response
| Control | Evidence | Owner |
|---------|----------|-------|
| Incident detection | Alertmanager → PagerDuty for critical alerts | SRE |
| Incident response plan | `docs/compliance/INCIDENT_RESPONSE.md` | Security |
| Breach notification SLA | 72 hours (GDPR Article 33) | Legal |

### CC7.3: Backup & Recovery
| Control | Evidence | Owner |
|---------|----------|-------|
| Automated backups | K8s CronJob + `scripts/backup-db.sh` | SRE |
| Backup encryption | S3 SSE-S3 or KMS | SRE |
| Recovery testing | Quarterly DR drill | SRE |
| Rollback runbook | `ROLLBACK.md` | SRE |

### CC7.4: Capacity Management
| Control | Evidence | Owner |
|---------|----------|-------|
| Horizontal scaling | K8s HPA for app and Celery workers | SRE |
| DB read replicas | `DATABASE_READ_REPLICA_URL` config | SRE |
| Load testing | k6 tests in `load-tests/` | SRE |

---

## CC8 — Change Management

### CC8.1: Change Authorization
| Control | Evidence | Owner |
|---------|----------|-------|
| PR approval process | Branch protection: 2 reviewers required | SRE |
| Production change log | `CHANGELOG.md` | Product |
| Emergency change procedure | Hotfix branch + post-hoc review | SRE |

### CC8.2: Change Testing
| Control | Evidence | Owner |
|---------|----------|-------|
| Unit tests | 218 backend tests, 5 frontend tests | Engineering |
| Integration tests | pytest with PostgreSQL + Redis in CI | Engineering |
| Load tests | k6 tests for staging | Engineering |
| Pre-prod validation | Staging environment mirrors production | SRE |

### CC8.3: Change Deployment
| Control | Evidence | Owner |
|---------|----------|-------|
| Blue/green or rolling deployment | K8s rolling update strategy | SRE |
| Automated rollback | `ROLLBACK.md` + database migration reversibility | SRE |
| Feature flags | LaunchDarkly or similar (recommended) | Product |

---

## CC9 — Risk Mitigation

### CC9.1: Vendor Risk
| Control | Evidence | Owner |
|---------|----------|-------|
| Vendor security review | AWS/GCP security assessments | Security |
| Subprocessor list | Documented in privacy policy | Legal |
| Data processing agreements | DPAs with cloud providers | Legal |

### CC9.2: Business Continuity
| Control | Evidence | Owner |
|---------|----------|-------|
| Business continuity plan | `docs/compliance/BCP.md` | SRE |
| Disaster recovery RTO/RPO | RTO: 4 hours, RPO: 24 hours | SRE |
| Critical vendor backup | Multi-AZ DB + S3 cross-region replication | SRE |

---

## A1 — Availability

### A1.1: Availability Commitments
| Control | Evidence | Owner |
|---------|----------|-------|
| Uptime SLA | 99.9% uptime commitment | SRE |
| Monitoring | Prometheus + external uptime checks | SRE |
| Incident communication | Status page + Slack alerts | SRE |

### A1.2: System Availability
| Control | Evidence | Owner |
|---------|----------|-------|
| Redundancy | Multi-AZ K8s cluster | SRE |
| Auto-scaling | HPA for CPU/memory thresholds | SRE |
| Circuit breakers | `app/core/circuit_breaker.py` | Engineering |

### A1.3: Recovery Point Objective
| Control | Evidence | Owner |
|---------|----------|-------|
| DB backups | Daily automated backups to S3 | SRE |
| Backup retention | 30 days | SRE |
| Point-in-time recovery | AWS RDS PITR (recommended) | SRE |

---

## C1 — Confidentiality

### C1.1: Confidentiality Commitments
| Control | Evidence | Owner |
|---------|----------|-------|
| NDA policy | Employee and contractor NDAs | Legal |
| Data classification | Public, Internal, Confidential, Restricted | Security |

### C1.2: Confidential Information Protection
| Control | Evidence | Owner |
|---------|----------|-------|
| Encryption at rest | PostgreSQL encryption + S3 SSE | SRE |
| Encryption in transit | TLS 1.3 (nginx/ingress) | SRE |
| Field-level encryption | Fernet for PII in `app/core/encryption.py` | Security |
| Access logging | `audit_logs` table tracks data access | Security |

---

## PI1 — Processing Integrity

### PI1.1: Data Processing Authorization
| Control | Evidence | Owner |
|---------|----------|-------|
| Data validation | Pydantic schemas + calculation validation | Engineering |
| Authorization checks | RBAC on all data endpoints | Security |

### PI1.2: Data Accuracy
| Control | Evidence | Owner |
|---------|----------|-------|
| Calculation engine tests | `tests/test_calculations.py` | Engineering |
| Input validation | Magic bytes + extension checks on upload | Engineering |
| Data lineage | Provenance tracking in `app/services/provenance.py` | Engineering |

### PI1.3: Data Completeness
| Control | Evidence | Owner |
|---------|----------|-------|
| Required field validation | Pydantic `Field(...)` | Engineering |
| Calculation completeness | All methodology parameters validated | Engineering |

---

## P1 — Privacy

### P1.1: Privacy Notice
| Control | Evidence | Owner |
|---------|----------|-------|
| Privacy policy | `/compliance/privacy-policy` | Legal |
| Cookie notice | Cookie banner (frontend) | Product |
| Data subject rights | GDPR erasure endpoint | Legal |

### P1.2: Consent
| Control | Evidence | Owner |
|---------|----------|-------|
| Consent management | Consent recorded at registration | Legal |
| Consent withdrawal | Account deletion triggers erasure | Legal |

### P1.3: Data Minimization
| Control | Evidence | Owner |
|---------|----------|-------|
| Collection limitation | Only required fields in schemas | Engineering |
| Retention limits | `DATA_RETENTION_YEARS_RAW_PHOTOS=7` | Legal |
| Automatic deletion | Celery task for expired data cleanup | Engineering |

---

## Audit Evidence Checklist

For SOC 2 Type II, auditors will request evidence for each control. Prepare:

- [ ] Screenshots of monitoring dashboards
- [ ] Sample log entries showing access control enforcement
- [ ] Pull request history showing code review
- [ ] Incident response tickets
- [ ] Backup restoration test results
- [ ] Penetration test reports
- [ ] Employee training completion records
- [ ] Vendor security assessment questionnaires
- [ ] Data processing agreements
- [ ] Access review meeting minutes

---

## Next Steps for SOC 2 Type II

1. **Select auditor** (e.g., Vanta, Drata, or traditional CPA firm)
2. **Gap assessment** (4–6 weeks)
3. **Remediation** (4–8 weeks)
4. **Type I audit** (point-in-time, 2–4 weeks)
5. **Observation period** (3–12 months for Type II)
6. **Type II audit** (2–4 weeks)
7. **Report issuance** (2–4 weeks)

**Estimated timeline:** 6–12 months from start to Type II report.
