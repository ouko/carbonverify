# CarbonVerify Architecture

This document provides a deep dive into the architecture and design decisions of CarbonVerify.

## Table of Contents

- [Design Principles](#design-principles)
- [System Boundaries](#system-boundaries)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Calculation Pipeline](#calculation-pipeline)
- [Lead Intelligence Engine](#lead-intelligence-engine)
- [Async Task System](#async-task-system)
- [Security Model](#security-model)
- [Error Handling](#error-handling)
- [Observability](#observability)

---

## Design Principles

1. **Auditability First**: Every data point has a SHA-256 provenance hash chain. Every calculation is reproducible.
2. **Human-in-the-Loop**: Automated pipelines flag uncertain data (<85% confidence) or quality gate failures for human review before registry submission.
3. **Methodology Agnostic**: Rules engines are parameterized per methodology (TPDDTEC v4, VM0050, VMR0006, AMS-II.G), not hardcoded.
4. **Conservative Crediting**: Monte Carlo 95% CI lower bound used for issuance recommendations, not mean.

---

## System Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  React 18  ←──→  Axios (auto-refresh)  ←──→  FastAPI       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                             │
│  JWT Auth  →  RBAC Middleware  →  Rate Limiting             │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   REST API   │    │  WebSocket   │    │  Webhooks    │
│  (CRUD +     │    │  (real-time  │    │  (IoT        │
│   calc runs) │    │   alerts)    │    │   providers) │
└──────┬───────┘    └──────────────┘    └──────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Ingestion│ │Validation│ │Calculation│ │   Reports    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │Provenance│ │  S3      │ │ VVB Liaison│ │ Review Queue│   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Lead Intelligence (Scrapers + Scorer)       │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐  │   │
│  │  │  CDM    │ │ Verra   │ │Gold Std │ │  Scorer  │  │   │
│  │  │Scraper  │ │Scraper  │ │Scraper  │ │  Engine  │  │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └──────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Data Layer                                 │
│  PostgreSQL 15  ←──→  Redis  ←──→  Celery Workers          │
│  (SQLAlchemy 2)      (Queue)       (Async Jobs)             │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. File Upload Flow

```
User uploads file
       │
       ▼
Magic-bytes detection (python-magic)
       │
       ▼
S3 upload: {project_id}/{source_type}/{timestamp}/{filename}
       │
       ▼
Celery task: process_uploaded_file
       │
       ├───► Excel/CSV → pandas → structured records
       ├───► PDF → pdfplumber + pytesseract OCR
       ├───► Image → PIL + Shapely (GPS extraction)
       └───► IoT → schema normalization
       │
       ▼
Validation Engine
       │
       ├───► JSON Schema validation
       ├───► GPS / temporal checks
       └───► Cross-reference verification
       │
       ▼
Confidence Score (0–1)
       │
       ├───► ≥0.85 → auto-accept
       └───► <0.85 → flag → HumanReviewQueue
       │
       ▼
Provenance Hash Chain
       │
       ▼
PostgreSQL: DataSource record
```

### 2. Calculation Flow

```
Operator triggers calculation
       │
       ▼
CalculationOrchestrator.run_full_pipeline()
       │
       ├───► fNRB Calculator
       │     └───► Inverse-distance weighted interpolation
       │           └───► CCP cap enforcement (0.50)
       │
       ├───► Emissions Quantifier
       │     ├───► Baseline emissions (IPCC Tier 1/2)
       │     ├───► Project emissions (efficiency ratio)
       │     └───► Net reductions
       │
       ├───► Leakage Detector
       │     ├───► Market leakage (price drop >15%)
       │     ├───► Activity shifting (stacking >20%)
       │     └───► Spatial leakage (bounding box)
       │
       ├───► Methodology Validator
       │     └───► Rules engine → compliance score (0–100)
       │
       └───► Uncertainty Engine
             ├───► Monte Carlo (10k iterations)
             └───► Tornado sensitivity analysis
       │
       ▼
CalculationRun record created
       │
       ├───► sensitivity_analysis → operator review
       └───► status = 'pending_approval'
       │
       ▼
Human Approval Gate
       │
       ├───► approved → available for report generation
       └───► rejected → operator notes → recalculate
```

### 3. Report Generation Flow

```
Operator requests report
       │
       ▼
ReportGenerator.build_context()
       │
       ├───► Project data
       ├───► CalculationRun results
       ├───► DataSource aggregation
       └───► KPT / survey statistics
       │
       ▼
Jinja2 Template Rendering
       │
       ├───► gs_tpddtec_v4.html
       └───► verra_vm0050.html
       │
       ▼
Quality Gates
       │
       ├───► Cross-reference validation
       ├───► Citation completeness
       ├───► Calculation consistency
       └───► Methodology compliance ≥70%
       │
       ├───► FAIL → HumanReviewQueue
       └───► PASS → PDF generation
       │
       ▼
WeasyPrint HTML → PDF
       │
       ▼
S3 storage + Report record
```

### 3.5 AI Methodology Designer Flow

```
Operator describes novel project activity
       │
       ▼
POST /methodology-generator/
       │
       ▼
GeneratedMethodology record (status = draft)
       │
       ▼
POST /{id}/analyze
       │
       ├───► Fits existing methodology? → YES → stop; recommend existing methodology
       └───► NO → gap analysis JSON (gaps, matches, recommendation)
       │
       ▼
POST /{id}/generate
       │
       ├───► Kimi API or fallback generator
       ├───► methodology JSON (applicability, baseline, boundary, leakage, monitoring)
       └───► quantification_scaffold JSON (equations, parameters, data sources, uncertainty)
       │
       ▼
Operator / VVB review
       │
       ├───► approve → status = approved → export Markdown
       ├───► reject → status = rejected + rejection_reason
       └───► revision_requested → status = revision_requested → back to draft
```

The generator is intentionally **human-in-the-loop**: the AI produces structured drafts, but only an operator or admin can transition the record out of `under_review`. All status transitions are written to `audit_logs`.

### 4. Registry Submission Flow

```
Operator submits report to registry
       │
       ▼
Quality Gate Check (final)
       │
       ├───► FAIL → blocked, HumanReviewQueue
       └───► PASS → proceed
       │
       ▼
Registry Client (Verra / Gold Standard)
       │
       ├───► submit_monitoring_report()
       └───► Exponential backoff retry (3 attempts)
       │
       ▼
Report.status = 'submitted'
       │
       ▼
RegistryPoller (daily Celery beat)
       │
       ├───► poll registry status
       ├───► update Report.status
       └───► auto-follow-up if SLA exceeded (14 days)
```

### 5. Lead Intelligence Flow

```
Celery Beat (daily) or Manual trigger
       │
       ▼
scrape_registries task
       │
       ├───► CDM Scraper (Playwright + BeautifulSoup)
       │     ├───► Live: Navigate search form, parse table
       │     └───► Fallback: Demo Kenya projects (9)
       │
       ├───► Verra Scraper (Playwright)
       │     ├───► Live: Angular grid (blocked → empty)
       │     └───► Fallback: Demo Kenya projects (5)
       │
       └───► Gold Standard Scraper (Playwright)
             ├───► Live: Public listing (blocked → empty)
             └───► Fallback: Demo Kenya projects (4)
       │
       ▼
Deduplication by external_id + registry_source
       │
       ▼
Upsert into Lead table
       │
       ▼
ScraperRun record per source (timestamp, count, status)
       │
       ▼
Frontend: "Last scraped" timestamps + per-source badges
```

---

## Database Schema

Key entities and relationships:

```
User ──► Project ──► DataSource
  │         │
  │         ├───► CalculationRun
  │         │       ├───► sensitivity_analysis (JSONB)
  │         │       └───► monte_carlo (JSONB)
  │         │
  │         ├───► Report
  │         │       ├───► status: draft → submitted → vvb_approved
  │         │       └───► quality_gates_result (JSONB)
  │         │
  │         ├───► FileUpload
  │         │       ├───► detected_type (magic bytes)
  │         │       ├───► file_hash_sha256
  │         │       └───► provenance chain
  │         │
  │         └───► HumanReviewQueue
  │                 ├───► item_type: data_source | calculation | report
  │                 ├───► severity: warning | error | critical
  │                 └───► status: open | in_review | approved | rejected
  │
  ├───► Role (admin | operator | developer | viewer)
  │
  └───► Lead ──► ScraperRun
        │            ├───► source: verra | gold_standard | cdm
        │            ├───► scraped_at
        │            ├───► count, created, updated
        │            └───► status: live | demo | error
        │
        ├───► registry_source
        ├───► stuck_score (0–100)
        ├───► priority (low | medium | high | critical)
        ├───► lead_status (new | contacted | qualified | proposal_sent | converted)
        ├───► crediting_period_end (deadline tracking)
        └───► days_in_status
```

Full schema definition: [`backend/app/models.py`](backend/app/models.py)

---

## Calculation Pipeline

### fNRB Spatial Interpolation

1. **Input**: Project latitude, longitude, assessment year, fuel type
2. **Process**:
   - Haversine distance to all 20 reference points
   - Inverse-distance weighted average (power=2, minimum 3 points)
   - Charcoal fuel type: +5% adjustment
   - CCP cap at 0.50 (flagged if capped without MoFuSS)
3. **Output**: `fnrb_value`, `uncertainty_range`, `source_reference`, `confidence_score`, `flagged`

### Emissions Quantification

1. **Baseline**: `fuel_consumption_kg_per_day × household_count × 365 × emission_factor × fnrb`
2. **Project**: Same formula with efficiency-ratio adjustment
   - `adjusted_fuel = baseline_fuel × (baseline_efficiency / project_efficiency)`
3. **Net**: `baseline - project - leakage`
4. **Monte Carlo**: 10,000 iterations
   - Fuel consumption: lognormal distribution
   - Thermal efficiency: beta distribution
   - Output: mean, median, std_dev, 95% CI, conservative estimate

### Leakage Detection

| Type | Trigger | Threshold |
|------|---------|-----------|
| Market | Fuel price in project area drops relative to control | >15% |
| Activity Shifting | Baseline stove still in use alongside project stove | >20% of households |
| Spatial | Stove installations outside project boundary | Bounding box + 5km buffer |

### Methodology Compliance Scoring

**TPDDTEC v4** (max 100):
- Efficiency ≥25% (25 pts)
- Durability score present (15 pts)
- Dissemination rate (15 pts)
- Tracking completeness ≥90% (20 pts)
- WBT/CCT presence (15 pts)
- Emissions data completeness (10 pts)

**VM0050** (max 100):
- Lab test required (20 pts)
- Usage rate caps: ≤75% (SUMs), ≤90% (other) (25 pts)
- KPT sample ≥30 households (25 pts)
- Duration ≥2 weeks (15 pts)
- Meter data completeness (15 pts)

**VMR0006**:
- Retroactive period ≤5 years (50 pts)
- Historical reconstruction (50 pts)

---

## Lead Intelligence Engine

### Persistent Browser Architecture

The scraper system uses a **singleton Playwright browser** that launches once and reuses across calls:

```
Launch Chromium (non-headless)
       │
       ▼
Apply stealth patches (playwright-stealth)
       │
       ▼
New context per scrape (user agent, viewport, locale)
       │
       ▼
Navigate → interact → parse → close context
       │
       ▼
Browser stays alive for next scrape (~18s vs ~36s first run)
```

- First scrape: ~36s (browser launch + page load)
- Subsequent scrapes: ~18s (browser reuse)
- Cleanup: `close_persistent_browser()` available for shutdown

### Stuck Score Algorithm

| Factor | Weight | Description |
|--------|--------|-------------|
| Time in Stage | 40 pts max | `days_in_status / 365 × 40` |
| Deadline Proximity | 25 pts max | Days until `crediting_period_end` |
| Verification Gap | 20 pts max | Days since `last_verification_date` |
| Methodology Complexity | 15 pts max | Based on methodology family |

**Priority Classification:**
- Critical: stuck_score ≥ 70
- High: stuck_score ≥ 50
- Medium: stuck_score ≥ 30
- Low: stuck_score < 30

### Scraper Sources

| Source | Live Status | Blocking Mechanism | Fallback |
|--------|-------------|-------------------|----------|
| CDM (UNFCCC) | ✅ Working | Incapsila (bypassed via non-headless + stealth) | 9 demo Kenya projects |
| Verra | ❌ Blocked | Cloudflare + Angular grid | 5 demo Kenya projects |
| Gold Standard | ❌ Blocked | API requires authentication | 4 demo Kenya projects |

---

## Async Task System

Celery configuration: [`backend/app/tasks/celery_app.py`](backend/app/tasks/celery_app.py)

| Task | Schedule | Purpose |
|------|----------|---------|
| `process_uploaded_file` | On-demand | File parsing pipeline |
| `generate_report_pdf` | On-demand | HTML → PDF compilation |
| `submit_report_to_registry` | On-demand | Registry API submission |
| `check_flagged_data_sources` | Every 5 min | Alert on low-confidence data |
| `generate_overdue_reports` | Every 1 hr | Auto-generate pending reports |
| `poll_registry_statuses` | Daily | Sync registry approval status |
| `send_registry_follow_ups` | Daily | Auto-follow-up after SLA |
| `scrape_registries` | Daily | Scrape carbon registries for leads |
| `score_leads` | Weekly | Re-calculate stuck scores |
| `check_lead_deadlines` | Daily | Alert on approaching crediting period ends |
| `lifecycle_scan` | Every 5 min | Drive project state machines forward autonomously |
| `human_review_sla_sweep` | Hourly | Auto-approve human-review items past 24h SLA |
| `remediation_sweep` | Every 15 min | Re-run stale failed auto-remediations |
| `dispatch_p0_escalations` | Every 60 s | Re-send undelivered P0 alerts (WhatsApp/SMS ≤60s) |
| `send_p1_escalations` | Every 30 min | Dispatch P1 email/push escalations within 2h SLA |
| `daily_escalation_digest` | Daily | Aggregate P2 + recent P0/P1 into operator digest |
| `run_synthetic_validation` | Every 15 min | Run 3 synthetic E2E journeys + record health snapshot |
| `check_methodology_updates` | Daily | Flag knowledge-base documents due for refresh |
| `generate_weekly_learning_report` | Weekly | Persist agent calibration / retraining report |

---

## Autonomous Agent Layer

Added 2026-11. Target operating model: **90% of workflows run without human touch, 9% queue for one-click approval, 1% escalate in real time.**

- **Orchestration** (`backend/app/orchestrator/`): `KimiClawOrchestrator` dispatches the 7 agents below on lifecycle transitions. Confidence scoring routes every decision: ≥0.95 auto-advance (learned per-agent thresholds from the learning loop may raise this), 0.85–0.95 queues a `HumanReviewQueue` item with 24h SLA (auto-approved by `human_review_sla_sweep` if unactioned), <0.85 pauses and raises an escalation. `advance_project` walks states with a visited-state loop guard; `lifecycle_scan` drives it on a 5-minute beat.
- **Agents** (`backend/app/agents/`): Ingestion (real upload validation, duplicate/out-of-range/stale detection), Calculation (fNRB/quantification/leakage/uncertainty engines + LLM plausibility check), Reporting (quality gates + draft completeness), VVB Liaison (registry polling + clarification drafting), Quality Control (statistical sampling, IQR outliers), Risk/Validation (additionality screening, red flags, conservative cap), Client Success (churn risk, upsell triggers). All use Kimi tool-calling (`KimiAPIClient.reason/chat_with_tools`) with deterministic heuristic fallback when no API key; every result carries `reasoning` + `evidence`.
- **Decision audit** (`agent_decisions` table, merkle-chained SHA-256): every routing and human resolution is recorded with explainable reasoning; `GET /api/v1/audit/{decision_id}`, `GET /api/v1/audit/decisions`, `POST /api/v1/audit/verify-chain`.
- **Self-healing** (`backend/app/remediation/`): shared `RemediationEngine` with 6 rule strategies (auto-correct, backoff+circuit-break, deadlock jitter retry, conservative fallback, interpolate/exclude, KB draft response). Every attempt logs before/after state hashes; 3 failed attempts escalate with the full hash-bearing failure chain. Orchestrator attempts automatic remediation on agent failure before routing.
- **Escalations** (`backend/app/escalations/`): `EscalationEvent` priorities P0 (all channels, ≤60s), P1 (email+push, ≤2h), P2 (daily digest). Channel adapters (WhatsApp/SMS/email/in-app pubsub) are no-op-safe without credentials. APIs under `/api/v1/escalations/` incl. composite `health/score`.
- **Continuous validation** (`backend/app/validation_engine/`): three synthetic E2E journeys (project developer, field enumerator offline→sync, calculation-anomaly recovery) run every 15 minutes with Merkle proofs anchored to Radix; `ValidationHealthSnapshot` scores the system (journey success 60% / remediation resolution 20% / escalation backlog 20%); a 7-day-below-90 streak blocks deployment via `scripts/pre_deploy_check.py`.
- **Knowledge & learning** (`backend/app/knowledge/`, `backend/app/learning/`): `MethodologyKnowledgeBase` (chunked methodology documents, pluggable embeddings — deterministic local by default, OpenAI-compatible optional — cosine search, RAG answers with citations, `/api/v1/knowledge/*`); `AgentLearningLoop` tracks human overrides, computes per-agent calibration (override rate, confidence-bucket accuracy), generates weekly retraining reports, and feeds learned thresholds back into the orchestrator (`/api/v1/learning/*`).
- **Operator UI**: Command Center gained `/command-center/escalations` (P0/P1/P2 inbox, acknowledge/resolve, delivery timeline) and `/command-center/health` (system score gauge + component breakdown + confidence trend); the review Inbox shows agent reasoning, confidence, and financial impact from the decision audit.

---

## Security Model

### Authentication
- JWT access tokens (15 min expiry)
- JWT refresh tokens (7 day expiry, stored in httpOnly cookie)
- Bcrypt password hashing

### Authorization (RBAC)

| Role | Permissions |
|------|------------|
| **admin** | Full access, user management |
| **operator** | Upload data, run calculations, approve reports, review queue |
| **developer** | API access, webhook integration, read-only dashboard |
| **viewer** | Read-only dashboard and reports |

### Data Protection
- `.env` excluded from version control (see `.gitignore`)
- S3 presigned URLs for file downloads (time-limited)
- All file hashes verified via SHA-256

---

## Error Handling

| Layer | Strategy |
|-------|----------|
| API | Structured JSON errors with `detail`, `code`, `field` |
| Celery | Dead letter queue for failed jobs; retry with exponential backoff |
| Registry Clients | 3 attempts with backoff on 5xx/timeout; structured logging |
| Validation | Confidence score + flagging instead of hard rejection |
| Scrapers | Live attempt → empty/error → demo fallback; `ScraperRun.status` tracks outcome |

---

## Observability

- **Structured Logging**: JSON format via `app/core/logging.py`
- **Health Checks**: `/health/` endpoint (DB + Redis)
- **Scraper Health**: `/api/v1/leads/health/scrapers` — per-source status
- **Key Metrics Logged**:
  - `calculation_complete` with all result fields
  - `quality_gates_complete` with pass/fail status
  - `registry_submission` with retry count
  - `file_processed` with detected type and confidence
  - `scraper_run_complete` with source, count, data_source, duration

---

## Technology Decisions

| Decision | Rationale |
|----------|-----------|
| **SQLAlchemy 2.0** | Native async support, type-safe queries |
| **Pydantic v2** | Fast validation, OpenAPI schema generation |
| **React Query** | Caching, background refetch, optimistic updates |
| **Zustand** | Minimal boilerplate vs Redux; adequate for auth+theme |
| **WeasyPrint** | HTML+CSS → PDF; easier to template than LaTeX |
| **Celery + Redis** | Mature async task queue; supports scheduling |
| **Alembic** | Database migration versioning; required for production |
| **Playwright** | Headful Chromium bypasses bot detection (Incapsula); persistent browser singleton |
| **playwright-stealth** | Patches Playwright fingerprints to avoid detection |
