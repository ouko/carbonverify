# Migration Rollback Procedures

This document describes how to safely roll back database migrations in production.

---

## Prerequisites

- `psql` client or database admin access
- Alembic installed in the deployment environment
- Current database backup (see DEPLOYMENT.md for backup procedures)

---

## Before Any Migration

### 1. Create a backup

```bash
# Docker Compose
docker-compose exec db pg_dump -U carbonverify -d carbonverify > backup_$(date +%Y%m%d_%H%M%S).sql

# Kubernetes
kubectl exec -it deploy/postgres -- pg_dump -U carbonverify -d carbonverify > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. Verify backup integrity

```bash
# Check backup file size (> 1KB for a non-empty DB)
ls -lh backup_*.sql

# Verify first and last lines
ghead -5 backup_*.sql
tail -5 backup_*.sql
```

### 3. Test migration in staging

```bash
# Apply to staging database first
alembic upgrade +1

# Run smoke tests against staging
pytest tests/ -m smoke -q
```

---

## Rollback Procedure

### Scenario: Bad migration applied to production

#### Step 1: Stop writes

```bash
# Scale API to 0 replicas to prevent new writes
kubectl scale deployment carbonverify-api --replicas=0

# Or in Docker Compose
docker-compose stop app celery-worker celery-beat
```

#### Step 2: Identify target revision

```bash
# View migration history
alembic history --verbose

# Current revision
alembic current
```

#### Step 3: Downgrade one revision

```bash
# Downgrade by exactly one migration
alembic downgrade -1
```

#### Step 4: Downgrade to specific revision

```bash
# Downgrade to a known-good revision (use the revision hash)
alembic downgrade <revision_hash>
```

#### Step 5: Verify database state

```bash
# Check current revision
alembic current

# Run health check
python -c "from app.main import app; print('OK')"
```

#### Step 6: Restore from backup (if downgrade fails)

```bash
# Stop all services
docker-compose stop app celery-worker celery-beat

# Restore from backup
docker-compose exec -T db psql -U carbonverify -d carbonverify < backup_YYYYMMDD_HHMMSS.sql

# Verify
docker-compose exec db psql -U carbonverify -c "SELECT COUNT(*) FROM users;"
```

#### Step 7: Resume services

```bash
# Kubernetes
kubectl scale deployment carbonverify-api --replicas=3

# Docker Compose
docker-compose start app celery-worker celery-beat
```

---

## Critical Migrations Requiring Special Handling

| Migration | Risk | Rollback Notes |
|-----------|------|----------------|
| Column deletion | High | Data loss; restore from backup only |
| Enum value removal | Medium | Downgrade re-adds value; existing rows unaffected |
| Table rename | Low | Downgrade renames back; no data loss |
| Type changes | Medium | May truncate data (e.g., VARCHAR → TEXT is safe, reverse is not) |
| Encrypted columns | Medium | Downgrade leaves encrypted data; decrypt before rollback |

---

## Emergency Contacts

- On-call engineer: `#incidents` Slack channel
- Database admin: `dba@carbonverify.io`
- Infrastructure lead: `infra@carbonverify.io`
