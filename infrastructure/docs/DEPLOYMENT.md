# CarbonVerify Production Deployment Guide

This document describes the complete infrastructure, deployment procedures, and operational runbooks for CarbonVerify in production.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Local Development (Docker Compose)](#local-development-docker-compose)
4. [AWS Infrastructure (Terraform)](#aws-infrastructure-terraform)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Monitoring & Alerting](#monitoring--alerting)
8. [Backup & Disaster Recovery](#backup--disaster-recovery)
9. [Security](#security)
10. [Operational Runbooks](#operational-runbooks)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Users                                       │
│                    (Web App, Mobile, API Clients)                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Cloudflare / Route 53                            │
│                     DNS + DDoS Protection + WAF                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AWS Application Load Balancer                        │
│                     SSL Termination + Rate Limiting                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AWS EKS (Kubernetes Cluster)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  App Pods    │  │ Celery Worker│  │ Celery Beat  │                  │
│  │  (3 replicas)│  │  (2 replicas)│  │  (1 replica) │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
│         │                   │                   │                       │
│         └───────────────────┴───────────────────┘                       │
│                             │                                           │
│                             ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │              AWS RDS (PostgreSQL 15) Multi-AZ                │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                             │                                           │
│                             ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │         AWS ElastiCache (Redis 7) - Session/Queue            │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                             │                                           │
│                             ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │              AWS S3 - File Storage + Backups                 │      │
│  └──────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- **AWS Account** with IAM permissions for EKS, RDS, ElastiCache, S3, ECR, VPC
- **Terraform** >= 1.5.0
- **kubectl** >= 1.28
- **AWS CLI** >= 2.0
- **Docker** + **Docker Compose**
- **Node.js** >= 20 + **npm**
- **Python** >= 3.11 + **uv**

---

## Local Development (Docker Compose)

### Quick Start

```bash
cd infrastructure

# Copy environment file
cp ../.env.example .env
# Edit .env with your values

# Start all services
docker-compose up --build

# Access URLs:
# - Frontend:    http://localhost:5173
# - API:         http://localhost:8000
# - API Docs:    http://localhost:8000/docs
# - Nginx Proxy: http://localhost
```

### Services

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| `db` | PostgreSQL 15 | 5432 | Primary database |
| `redis` | Redis 7 | 6379 | Cache / Celery broker |
| `app` | FastAPI | 8000 | Backend API |
| `celery-worker` | Celery | - | Background tasks |
| `celery-beat` | Celery Beat | - | Scheduled tasks |
| `nginx` | Nginx | 80/443 | Reverse proxy |
| `frontend` | Vite React | 5173 | Frontend dev server |

### Health Checks

All services include Docker health checks:

```bash
# Check all service health
docker-compose ps

# View logs
docker-compose logs -f app
docker-compose logs -f celery-worker
```

---

## AWS Infrastructure (Terraform)

### State Management

Terraform state is stored in S3 with DynamoDB locking:

```bash
# Create state bucket and lock table (one-time setup)
aws s3 mb s3://carbonverify-terraform-state --region us-east-1
aws dynamodb create-table \
  --table-name carbonverify-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### Deploy Production Infrastructure

```bash
cd infrastructure/terraform/environments/production

# Initialize
terraform init

# Plan
terraform plan -var="db_password=$(openssl rand -base64 32)"

# Apply
terraform apply -var="db_password=$(openssl rand -base64 32)"

# Outputs
terraform output
```

### Infrastructure Components

#### VPC Module
- **CIDR**: `10.0.0.0/16`
- **AZs**: 3 availability zones
- **Public Subnets**: 3 (for ALB, NAT Gateways)
- **Private Subnets**: 3 (for EKS nodes, RDS, ElastiCache)
- **NAT Gateways**: 1 per AZ (production), 1 shared (staging)

#### EKS Module
- **Version**: 1.29
- **Node Groups**: Managed node groups with SPOT (staging) / ON_DEMAND (production)
- **Addons**: CoreDNS, kube-proxy, VPC CNI, EBS CSI
- **IRSA**: Load Balancer Controller, Cluster Autoscaler, External DNS

#### RDS Module
- **Engine**: PostgreSQL 15.4
- **Instance**: `db.r6g.large` (production), `db.t3.medium` (staging)
- **Storage**: GP3, encrypted, 100GB base (production)
- **Multi-AZ**: Enabled in production
- **Backups**: 30-day retention, daily window 03:00-04:00 UTC
- **Performance Insights**: Enabled in production

#### ElastiCache Module
- **Engine**: Redis 7.1
- **Node Type**: `cache.r6g.large` (production), `cache.t3.micro` (staging)
- **Cluster Mode**: 2 nodes with Multi-AZ (production)
- **Encryption**: At-rest + in-transit

#### S3 Module
- **Uploads Bucket**: Versioned, lifecycle to IA after 90 days, Glacier after 365 days
- **Backups Bucket**: Versioned, cross-region replication to us-west-2 (production)
- **Encryption**: SSE-S3
- **Public Access**: Blocked

#### ECR Module
- **Repositories**: `carbonverify-app`, `carbonverify-frontend`
- **Image Tag Mutability**: IMMUTABLE
- **Scanning**: On-push
- **Lifecycle**: Keep last 30 images

---

## Kubernetes Deployment

### Structure

```
infrastructure/k8s/
├── base/                          # Base manifests (production defaults)
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── app-deployment.yaml
│   ├── celery-worker-deployment.yaml
│   ├── celery-beat-deployment.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   └── backup-cronjob.yaml
└── overlays/
    ├── staging/                   # Staging overrides
    │   └── kustomization.yaml
    └── production/                # Production overrides
        └── kustomization.yaml
```

### Deploy to Staging

```bash
# Update image tags
cd infrastructure/k8s/overlays/staging
kustomize edit set image <ECR_REGISTRY>/carbonverify-app=123456789012.dkr.ecr.us-east-1.amazonaws.com/carbonverify-app:staging-latest
kustomize edit set image <ECR_REGISTRY>/carbonverify-frontend=123456789012.dkr.ecr.us-east-1.amazonaws.com/carbonverify-frontend:staging-latest

# Apply
kustomize build . | kubectl apply -f -

# Verify rollout
kubectl rollout status deployment/staging-carbonverify-app -n carbonverify-staging
```

### Deploy to Production

```bash
cd infrastructure/k8s/overlays/production
kustomize build . | kubectl apply -f -

# Monitor rollout
kubectl rollout status deployment/prod-carbonverify-app -n carbonverify
kubectl rollout status deployment/prod-carbonverify-celery-worker -n carbonverify
```

### Scaling

```bash
# Manual scale
kubectl scale deployment/carbonverify-app --replicas=5 -n carbonverify

# View HPA status
kubectl get hpa -n carbonverify

# View pod distribution
kubectl get pods -n carbonverify -o wide
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

```
Push/PR
  │
  ├── Lint Backend (ruff, mypy)
  ├── Lint Frontend (eslint, tsc)
  │
  ├── Test Backend (pytest, coverage >80%)
  ├── Test Frontend (jest, coverage)
  │
  ├── Build & Push Docker Images (ECR)
  │
  ├── Deploy Staging (auto on develop)
  │
  ├── Integration Tests (Postman/Newman)
  │
  └── Deploy Production (manual approval on main)
```

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ROLE_ARN` | OIDC role for GitHub Actions |
| `CODECOV_TOKEN` | Codecov upload token |

### Rollback

Automatic rollback triggers on:
- Health check failure after deployment
- Integration test failure
- Smoke test failure

```bash
# Manual rollback
kubectl rollout undo deployment/prod-carbonverify-app -n carbonverify
```

---

## Monitoring & Alerting

### Prometheus

Deployed via Prometheus Operator in the `monitoring` namespace:

```bash
# Port-forward Prometheus
kubectl port-forward svc/prometheus-k8s 9090:9090 -n monitoring

# Access: http://localhost:9090
```

### Grafana

```bash
# Port-forward Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring

# Access: http://localhost:3000
# Default credentials: admin / admin
```

### Key Alerts

| Alert | Severity | Condition | Response |
|-------|----------|-----------|----------|
| `HighErrorRate` | critical | Error rate > 5% for 5m | Page on-call engineer |
| `HighLatency` | warning | P95 latency > 2s for 5m | Investigate app/db |
| `CeleryQueueBacklog` | warning | Queue depth > 100 for 10m | Scale workers |
| `LowAgentConfidence` | warning | Avg confidence < 70% for 15m | Review agent data |
| `VVBDeadlineMissed` | critical | Any missed deadline | Immediate escalation |
| `PotentialDataBreach` | critical | > 10 suspicious accesses | Security team alert |

### PagerDuty Integration

Critical alerts are routed to PagerDuty via Alertmanager:

```yaml
# Alertmanager configuration snippet
route:
  group_by: ['alertname', 'severity']
  receiver: 'pagerduty-critical'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
    - match:
        severity: warning
      receiver: 'slack-warnings'
```

---

## Backup & Disaster Recovery

### PostgreSQL Backups

- **Frequency**: Daily at 03:00 UTC
- **Retention**: 30 days
- **Storage**: S3 `carbonverify-backups-production/postgres/daily/`
- **Cross-Region Replication**: us-west-2 (production only)
- **Encryption**: SSE-S3

```bash
# Manual backup
./infrastructure/backup/postgres-backup.sh

# Restore from latest backup
./infrastructure/backup/postgres-restore.sh

# Restore from specific backup
./infrastructure/backup/postgres-restore.sh s3://carbonverify-backups-production/postgres/daily/carbonverify_production_20240115_030000.sql.gz
```

### File Storage (S3)

- **Versioning**: Enabled
- **Cross-Region Replication**: Enabled (production)
- **Lifecycle**: IA after 90 days, Glacier after 365 days

### Recovery Objectives

| Metric | Target | Implementation |
|--------|--------|----------------|
| **RTO** | 4 hours | Automated EKS pod recovery, RDS Multi-AZ failover |
| **RPO** | 1 hour | Continuous S3 replication, daily backups + WAL |

### Disaster Recovery Drill

Conducted annually:
1. Simulate complete region failure
2. Restore infrastructure in DR region
3. Restore database from cross-region backup
4. Verify application functionality
5. Document lessons learned

---

## Security

### Network Security

- **VPC**: Private subnets for all compute; public subnets only for ALB
- **Security Groups**: Least-privilege access between services
- **WAF**: AWS WAF with OWASP Top 10 rules
- **DDoS**: AWS Shield Standard + Cloudflare (optional)

### Data Security

- **Encryption at Rest**: RDS, ElastiCache, S3, EBS
- **Encryption in Transit**: TLS 1.3 for all external, TLS 1.2+ internal
- **Secrets**: Kubernetes Secrets (staging), AWS Secrets Manager (production)
- **Key Rotation**: Annual JWT secret rotation

### Compliance

- **Kenya DPA**: Data subject request handling, breach notification (72h SLA)
- **Audit Logging**: All API calls logged to `audit_logs` table + S3
- **Blockchain Anchoring**: Radix DLT for immutable audit trail

---

## Operational Runbooks

### Restarting a Service

```bash
# Restart app deployment
kubectl rollout restart deployment/prod-carbonverify-app -n carbonverify

# Restart celery workers
kubectl rollout restart deployment/prod-carbonverify-celery-worker -n carbonverify
```

### Checking Logs

```bash
# App logs
kubectl logs -f deployment/prod-carbonverify-app -n carbonverify

# Celery worker logs
kubectl logs -f deployment/prod-carbonverify-celery-worker -n carbonverify

# Search logs with stern
stern carbonverify-app -n carbonverify
```

### Database Maintenance

```bash
# Connect to RDS
kubectl run psql --rm -it --image=postgres:15-alpine \
  -- psql postgresql://user:pass@postgres:5432/carbonverify

# Check connection pool usage
SELECT count(*) FROM pg_stat_activity;
```

### Scaling for High Load

```bash
# Emergency scale up
kubectl scale deployment/prod-carbonverify-app --replicas=10 -n carbonverify
kubectl scale deployment/prod-carbonverify-celery-worker --replicas=8 -n carbonverify

# HPA will auto-scale based on CPU/memory, but manual override works for emergencies
```

---

## Support

For issues or questions:
- **Slack**: #carbonverify-ops
- **PagerDuty**: CarbonVerify On-Call
- **Runbook Updates**: Submit PR to `infrastructure/docs/`
