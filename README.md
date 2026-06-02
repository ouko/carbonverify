# CarbonVerify

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)](https://react.dev/)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey.svg)]()

**CarbonVerify** is an automated carbon credit MRV (Measurement, Reporting, and Verification) preparation platform for improved cookstove and clean energy projects. It streamlines the entire pipeline from raw field data → emissions calculations → audit-ready monitoring reports → registry submission. It also includes a **Lead Intelligence Engine** that scrapes carbon registries to identify high-potential project developers and a **Command Center** for operations management.

---

## Table of Contents

- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Backend](#backend)
  - [Calculation Engine](#calculation-engine)
  - [Data Ingestion](#data-ingestion)
  - [Report Generation](#report-generation)
  - [VVB Liaison](#vvb-liaison)
  - [Lead Intelligence Engine](#lead-intelligence-engine)
  - [API Endpoints](#api-endpoints)
- [Frontend](#frontend)
- [Testing](#testing)
- [Deployment](#deployment)
- [Methodologies Supported](#methodologies-supported)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Module | Capability |
|--------|-----------|
| **Data Ingestion** | Multi-format upload (Excel, CSV, PDF, Images, IoT webhooks) with magic-bytes detection and S3 storage |
| **Data Validation** | JSON Schema validation, GPS/temporal checks, cross-reference verification, confidence scoring (0–1) |
| **Workflow Validation Engine** | Enterprise-grade autonomous QA with JSON-defined workflow graphs, cryptographic proof chains (Merkle trees), synthetic actor factory, auto-remediation, and human escalation gates |
| **Calculation Engine** | fNRB spatial interpolation, IPCC Tier 1/2 emissions quantification, Monte Carlo uncertainty (10k iterations), leakage detection, methodology compliance scoring |
| **Report Generator** | Jinja2 HTML templates → WeasyPrint PDF; auto-citations, cross-reference validation, quality gates |
| **VVB Liaison** | Automated registry submission (Verra / Gold Standard), status polling, SLA tracking, auto-drafted clarification responses |
| **Lead Intelligence** | Playwright-based scraper for Verra, Gold Standard, and CDM registries; stuck-score algorithm; CRM-style lead pipeline |
| **Command Center** | Operations dashboard with inbox, project grid, VVB pipeline, quality metrics, and agent performance monitoring |
| **Provenance** | SHA-256 hash chain: raw source → extraction → transformations → validation → storage |
| **Human Review Queue** | Flagged data and quality-gate failures route to operator review with approval workflows |

---

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   React 18  │────▶│  FastAPI    │────▶│  PostgreSQL 15  │
│  Frontend   │◀────│   Backend   │◀────│  (SQLAlchemy 2) │
└─────────────┘     └──────┬──────┘     └─────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌──────────┐
        │  Redis  │  │  Celery │  │   S3     │
        │ (Queue) │  │ Workers │  │ (Files)  │
        └─────────┘  └─────────┘  └──────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, React Query v5, Zustand, React Router v6, Recharts, Lucide icons |
| **Backend** | FastAPI, Python 3.14, SQLAlchemy 2.0, Alembic, Pydantic v2, Celery |
| **Database** | PostgreSQL 15 (JSONB, UUID, ARRAY) |
| **Cache / Queue** | Redis |
| **PDF** | WeasyPrint (HTML → PDF) |
| **Scraping** | Playwright (Chromium) + playwright-stealth + BeautifulSoup4 + lxml |
| **DevOps** | Docker Compose, health checks, structured JSON logging |

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- [Node.js](https://nodejs.org/) 18+ (for local frontend dev)
- [Python](https://www.python.org/) 3.14+ + [uv](https://github.com/astral-sh/uv) (for local backend dev)
- [Playwright](https://playwright.dev/) browsers (for lead scraping):
  ```bash
  cd backend && source .venv/bin/activate && playwright install chromium
  ```

### Docker Compose (Recommended)

```bash
# 1. Clone and enter the project
git clone https://github.com/ouko/carbonverify.git
cd carbonverify

# 2. Environment
cp .env.example .env

# 3. Start all services
docker-compose up --build

# 4. Access
# Frontend:  http://localhost:5173
# API Docs:  http://localhost:8000/docs
# API Base:  http://localhost:8000
```

### Services

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| PostgreSQL | `cv-db` | 5432 | Primary data store |
| Redis | `cv-redis` | 6379 | Celery broker + cache |
| FastAPI | `cv-app` | 8000 | REST API |
| Celery Worker | `cv-celery-worker` | — | Async task processing |
| Celery Beat | `cv-celery-beat` | — | Scheduled tasks |
| ClamAV | `cv-clamav` | — | Virus scanning for uploads |
| Frontend | `cv-frontend` | 5173 | Vite dev server |

### Demo Accounts

After running `python -m scripts.seed_demo_data`, log in with any of these accounts (all use password `DemoPass123!`):

| Email | Role |
|-------|------|
| `admin@carbonverify.demo` | Admin |
| `operator@carbonverify.demo` | Operator |
| `developer@carbonverify.demo` | Developer |
| `viewer@carbonverify.demo` | Viewer |
| `buyer@carbonverify.demo` | Buyer |
| `seller@carbonverify.demo` | Seller |
| `compliance@carbonverify.demo` | Compliance |
| `field@carbonverify.demo` | Field Manager |

### Local Backend Development

```bash
cd backend

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Install Playwright browsers (required for lead scraping)
playwright install chromium

# Run migrations
alembic upgrade head

# Seed demo data
python -m scripts.seed_demo_data

# Start server
uvicorn app.main:app --reload --port 8000
```

### Local Frontend Development

```bash
cd frontend
npm install
npm run dev
```

**CORS note:** Do not set `VITE_API_URL` in `frontend/.env.local`. The Vite dev server proxies API calls to `localhost:8000` automatically via `vite.config.ts`. Setting a direct API URL causes CORS issues because the backend and frontend run on different origins locally.

### Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
# 264 tests covering calculation engine, reports, VVB pipeline, lead intelligence, auth, admin
```

### Local Development Scripts

Convenience scripts in `scripts/` for hybrid local development:

| Script | Purpose |
|--------|---------|
| `./scripts/setup-local.sh` | One-time first setup: installs deps, starts Docker infra, runs migrations, seeds demo data |
| `./scripts/start-local.sh` | Starts everything (Docker infra + backend + frontend + Celery) |
| `./scripts/start-local.sh --infra` | Start only Docker infra (db + redis) |
| `./scripts/start-local.sh --app` | Start only backend/frontend/Celery (assumes infra is running) |
| `./scripts/stop-local.sh` | Stops everything |
| `./scripts/stop-local.sh --app` | Stop only backend/frontend/Celery |
| `./scripts/stop-local.sh --infra` | Stop only Docker infra |
| `./scripts/status-local.sh` | Shows what's running, ports, health checks, and recent logs |
| `./scripts/seed-local.sh` | Truncates all data and re-runs the demo seed script |

Logs are written to `.local-logs/` and PIDs are tracked in `.local-dev.pids`.

---

## Project Structure

```
carbonverify/
├── docker-compose.yml          # Full stack orchestration
├── .env.example                # Environment template
├── README.md                   # This file
├── ARCHITECTURE.md             # Deep-dive architecture doc
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/                # Database migrations
│   ├── app/
│   │   ├── main.py             # FastAPI application entry
│   │   ├── config.py           # Pydantic settings
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   ├── schemas.py          # Pydantic request/response schemas
│   │   ├── database.py         # Async engine + session
│   │   ├── api/                # Route handlers
│   │   ├── auth/               # JWT + bcrypt + RBAC
│   │   ├── calculations/       # Emissions calculation engine
│   │   ├── services/           # File detection, validation, S3, provenance
│   │   │   └── lead_intelligence/  # Registry scrapers + scoring
│   │   ├── reports/            # Jinja2 templates + PDF compilation
│   │   ├── tasks/              # Celery async jobs
│   │   └── vvb_liaison/        # Registry clients + auto-responder + polling
│   └── tests/
│       ├── test_calculations.py   # 43 tests (5 reference cases)
│       ├── test_reports.py        # 21 tests
│       ├── test_lead_api.py       # 7 tests
│       ├── test_lead_scorer.py    # 11 tests
│       ├── test_lead_scrapers.py  # 7 tests
│       └── test_orchestrator.py   # 24 tests
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── tsconfig.json
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── pages/              # Route pages (main app + command center)
        ├── components/         # Reusable UI + Layout shells
        ├── hooks/              # React Query hooks
        ├── services/           # API client (Axios + auto-refresh)
        ├── stores/             # Zustand (auth, theme, notifications)
        └── types/              # Shared TS types
```

---

## Backend

### Calculation Engine

The calculation engine is the core of CarbonVerify. It produces audit-ready emissions estimates aligned with IPCC guidelines and major carbon standards.

#### Modules

| Module | File | Description |
|--------|------|-------------|
| **fNRB Calculator** | `calculations/fnrb_calculator.py` | Inverse-distance weighted spatial interpolation across 20 geo-reference points; CCP cap at 0.50; fuel-specific adjustments (charcoal +5%) |
| **Emissions Quantifier** | `calculations/emissions_quantifier.py` | Baseline/project/net emissions using IPCC Tier 1/2 factors; efficiency-ratio adjustment; Monte Carlo 10k iterations with lognormal fuel + beta efficiency distributions |
| **Leakage Detector** | `calculations/leakage_detector.py` | Market price leakage (>15% threshold), stove stacking (>20% baseline use), spatial bounding-box checks |
| **Methodology Validator** | `calculations/methodology_validator.py` | Rules engines for TPDDTEC v4, VM0050, VMR0006; 0–100 compliance scoring with gap identification |
| **Uncertainty Engine** | `calculations/uncertainty_engine.py` | Tornado sensitivity analysis; conservative crediting via 95% CI lower bound |

#### Reference Test Cases

Five real-world verified projects are encoded as reference tests (`tests/test_calculations.py`):

1. **EcoZoom Kenya** — wood-fired rocket stoves
2. **BURN Kenya** — charcoal jiko stoves
3. **Envirofit Guatemala** — LPG adoption
4. **Toyola Ghana** — charcoal-efficient stoves
5. **Nepal Biogas** — biogas digesters

All 43 unit tests pass with computed physics within ±5% of verified baselines.

### Data Ingestion

```
Upload (multipart) → Magic-bytes detection → S3 storage
                           ↓
                    Celery task queue
                           ↓
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           Excel/CSV    PDF         Images
           (pandas)   (pdfplumber   (PIL +
                      + OCR)        Shapely)
```

- **S3 path pattern:** `{project_id}/{source_type}/{timestamp}/{filename}`
- **IoT webhooks:** `POST /api/v1/webhooks/iot/{project_id}` — auto-detects KOKO, BURN, generic GSM payloads
- **Validation engine:** Confidence score 0–1; auto-flagged if <0.85
- **Provenance:** SHA-256 hash chain maintained end-to-end

### Report Generation

```
DB Query → Build Context → Jinja2 Template → HTML
                                              ↓
                                    Cross-ref validation
                                    Citation completeness
                                    Quality gates
                                              ↓
                                         WeasyPrint
                                              ↓
                                            PDF
```

- **Templates:** Gold Standard TPDDTEC v4, Verra VM0050
- **Auto-citation:** Every statistic linked to IPCC tables / methodology sections
- **Quality gates:** Block submission if compliance < 70% or missing citations
- **Fallback:** If WeasyPrint unavailable, exports as HTML

### VVB Liaison

| Component | File | Purpose |
|-----------|------|---------|
| Registry Clients | `vvb_liaison/registry_clients/` | Verra + Gold Standard + Kenya National APIs with exponential-backoff retry |
| Auto-Responder | `vvb_liaison/auto_responder.py` | Classifies VVB queries (fNRB, sample size, etc.) and drafts responses from methodology KB |
| Polling | `vvb_liaison/polling.py` | Daily sync of registry statuses; auto-follow-up after 14-day SLA |
| Email Templates | `vvb_liaison/email_templates/` | Jinja2 HTML templates for submissions, follow-ups, clarifications |

### Lead Intelligence Engine

The Lead Intelligence Engine scrapes carbon registries to discover and score potential clients.

#### Registry Scrapers

| Source | Status | Data Source | Notes |
|--------|--------|-------------|-------|
| **CDM (UNFCCC)** | ✅ Live | Playwright + BeautifulSoup | Non-headless Chromium bypasses Incapsula; ~18s per scrape |
| **Verra** | ⚠️ Demo | Demo data | Angular grid blocked by Cloudflare; 5 realistic Kenya projects |
| **Gold Standard** | ⚠️ Demo | Demo data | API requires auth; 4 realistic Kenya projects |

Set `LEAD_SCRAPER_MODE=live` in `.env` to attempt live scraping (falls back to demo on failure).

#### Scoring Algorithm

Each lead receives a **Stuck Score** (0–100) based on:
- Time in current stage (40 pts max)
- Deadline proximity (25 pts max)
- Verification gap (20 pts max)
- Methodology complexity (15 pts max)

High scores (>70) indicate urgent renewal/reverification opportunities.

#### Scraper Run History

Every scrape execution is recorded in the `scraper_runs` table with per-source counts, timestamps, and status. The frontend displays last-scraped timestamps and allows manual re-scraping.

#### API Endpoints (Leads)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/leads/` | List all leads |
| `POST` | `/api/v1/leads/` | Create a manual lead |
| `GET` | `/api/v1/leads/{id}` | Get lead detail |
| `PATCH` | `/api/v1/leads/{id}` | Update lead (status, notes, priority) |
| `DELETE` | `/api/v1/leads/{id}` | Delete a lead |
| `POST` | `/api/v1/leads/{id}/score` | Re-calculate stuck score |
| `POST` | `/api/v1/leads/scrape` | Run scrapers (all or per-registry) |
| `GET` | `/api/v1/leads/stats/dashboard` | Lead aggregate stats |
| `GET` | `/api/v1/leads/health/scrapers` | Scraper health check |
| `GET` | `/api/v1/leads/scraper-history` | Per-source last scrape timestamps |

### API Endpoints (Core)

> **Pagination:** All list endpoints support `skip` (offset) and `limit` (page size) query parameters. Defaults vary by endpoint (typically 50–100 items); maximum is 200–500. Example: `GET /api/v1/projects?skip=0&limit=50`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/register` | Create account |
| `POST` | `/api/v1/auth/login` | JWT access + refresh tokens (returns `mfa_required` if MFA enabled) |
| `POST` | `/api/v1/auth/mfa/verify` | Verify TOTP or backup code during MFA login |
| `POST` | `/api/v1/auth/mfa/confirm` | Confirm MFA setup (returns 10 backup codes) |
| `POST` | `/api/v1/auth/mfa/regenerate-backup-codes` | Regenerate MFA backup codes |
| `POST` | `/api/v1/auth/forgot-password` | Request password reset email |
| `POST` | `/api/v1/auth/reset-password` | Reset password with token |
| `POST` | `/api/v1/auth/refresh` | Rotate access token |
| `GET` | `/api/v1/auth/oauth/{provider}` | Initiate OAuth login (google, microsoft, okta) |
| `GET` | `/api/v1/auth/oauth/{provider}/callback` | OAuth callback |
| `POST` | `/api/v1/auth/oauth/{provider}/link` | Link OAuth account |
| `DELETE` | `/api/v1/auth/oauth/{provider}/unlink` | Unlink OAuth account |
| `GET` | `/api/v1/auth/oauth/accounts` | List linked OAuth accounts |
| `POST` | `/api/v1/api-keys/` | Create API key (returns full key once) |
| `GET` | `/api/v1/api-keys/` | List API keys |
| `DELETE` | `/api/v1/api-keys/{id}` | Revoke API key |
| `GET` | `/api/v1/users/me` | Current user profile |
| `POST` | `/api/v1/projects` | Create project |
| `GET` | `/api/v1/projects` | List projects |
| `GET` | `/api/v1/projects/{id}` | Project detail |
| `POST` | `/api/v1/projects/{id}/upload` | Multipart file upload |
| `GET` | `/api/v1/projects/{id}/data-sources` | List data sources |
| `POST` | `/api/v1/calculations/projects/{id}/calculate` | Run full calculation pipeline |
| `GET` | `/api/v1/calculations/{id}` | Get calculation run |
| `POST` | `/api/v1/calculations/{id}/approve` | Human approval gate |
| `POST` | `/api/v1/reports/generate` | Generate monitoring report |
| `POST` | `/api/v1/reports/{id}/submit` | Submit to registry |
| `GET` | `/api/v1/review-queue` | Human review queue |
| `POST` | `/api/v1/review-queue/{id}/approve` | Approve flagged item |
| `POST` | `/api/v1/webhooks/iot/{project_id}` | IoT data ingestion |

---

## Frontend

- **State Management:** Zustand for auth + theme + notifications; React Query for server state
- **Routing:** Protected routes with permission-based access (`AdminRoute` checks specific permissions, not just role). RBAC middleware supports both role-based and explicit permission grants
- **Data Viz:** Recharts for dashboard metrics
- **Styling:** Tailwind CSS with dark mode (class strategy)
- **API Client:** Axios with automatic token refresh on 401
- **Pagination:** All list pages use consistent client-side pagination (Prev/Next controls, "Showing X–Y of Z" text) with server-side `skip`/`limit` support on all backend list endpoints

### Pages — Main App (`Layout`)

| Route | Page | Role |
|-------|------|------|
| `/login` | Login | Public |
| `/` | Dashboard | Any |
| `/projects` | Projects List | Any |
| `/projects/:id` | Project Detail | Any |
| `/projects/new` | New Project | Operator+ |
| `/data-sources` | Data Sources | Operator+ |
| `/calculations` | Calculations | Operator+ |
| `/reports` | Reports | Operator+ |
| `/review-queue` | Review Queue | Operator+ |
| `/field` | Field Dashboard | Operator+ |
| `/security` | Security Settings | Admin |
| `/audit` | Audit Log | Admin |
| `/compliance` | Compliance Dashboard | Admin |
| `/leads` | Lead Intelligence | Any |
| `/brokerage` | Brokerage | Any |
| `/tokenization` | Tokenization | Any |
| `/corporate` | Corporate Dashboard | Any |

### Pages — Command Center (`CommandLayout`)

| Route | Page | Description |
|-------|------|-------------|
| `/command-center/inbox` | Inbox | Priority queue / human review |
| `/command-center/projects` | Projects Grid | Grid view of all projects |
| `/command-center/vvb` | VVB Pipeline | Validation & Verification Body pipeline |
| `/command-center/quality` | Quality Metrics | Quality metrics dashboard |
| `/command-center/agents` | Agent Performance | AI agent performance monitoring |
| `/command-center/settings` | Settings | Notifications, automation, digest mode |

The Command Center sidebar includes a **← CarbonVerify** link back to the main dashboard.

---

## Testing

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_calculations.py` | 43 | fNRB, emissions, leakage, methodology, uncertainty, full pipeline, 5 reference cases |
| `test_reports.py` | 21 | Citations, cross-references, quality gates, report generation, VVB auto-responder, registry polling |
| `test_lead_api.py` | 7 | CRUD, scoring, scraping endpoints |
| `test_lead_scorer.py` | 11 | Stuck score algorithm, priority classification |
| `test_lead_scrapers.py` | 7 | CDM, Verra, Gold Standard scrapers with demo fallback |
| `test_orchestrator.py` | 24 | Calculation orchestration, pipeline integration |
| `test_auth.py` | 20 | Login, MFA, session management, invite flow, password policies, rate limiting |
| `test_users.py` | 18 | Admin CRUD, permissions, role-based access control, pagination |
| `test_admin.py` | 8 | Stats, session management, global analytics, batched queries |

---

## Deployment

### Docker Compose (Production-oriented)

The included `docker-compose.yml` defines services with health checks:

```yaml
services:
  db:       # PostgreSQL 15
  redis:    # Redis 7
  app:      # FastAPI (depends on db, redis)
  celery-worker:  # Task worker
  celery-beat:    # Scheduled tasks
  frontend:       # Vite production preview
```

Run migrations on first deploy:
```bash
docker-compose exec app alembic upgrade head
```

### Environment Variables

See `.env.example` for all required variables. Key ones:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL async connection string |
| `REDIS_URL` | Redis connection for Celery |
| `SECRET_KEY` | JWT signing key (rotate in production) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 credentials |
| `S3_BUCKET_NAME` | File storage bucket |
| `ENVIRONMENT` | `development` or `production` |
| `LEAD_SCRAPER_MODE` | `live` or `demo` (controls scraper behavior) |
| `WHATSAPP_VERIFY_TOKEN` | Meta webhook verification token for WhatsApp bot |
| `WHATSAPP_APP_SECRET` | Meta app secret for webhook signature validation |
| `IOT_WEBHOOK_SECRET` | Shared secret for IoT webhook HMAC signature verification |
| `OAUTH_GOOGLE_CLIENT_ID` / `OAUTH_GOOGLE_CLIENT_SECRET` | Google OAuth credentials |
| `OAUTH_MICROSOFT_CLIENT_ID` / `OAUTH_MICROSOFT_CLIENT_SECRET` | Microsoft OAuth credentials |
| `OAUTH_OKTA_CLIENT_ID` / `OAUTH_OKTA_CLIENT_SECRET` / `OAUTH_OKTA_DOMAIN` | Okta OAuth credentials |
| `AWS_SES_FROM_EMAIL` | From address for password reset / security emails |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | SMTP fallback for email service |
| `SIEM_ENDPOINT` | Splunk HEC or generic SIEM HTTP endpoint |
| `SIEM_TOKEN` | SIEM authentication token |
| `SIEM_SOURCE` | SIEM source field (default: `carbonverify`) |
| `SIEM_INDEX` | SIEM index field (default: `main`) |
| `PROXY_URL` | HTTP proxy for scraper IP rotation |
| `SCRAPER_FORCE_HEADLESS` | `true` to force headless Playwright in production |
| `SCRAPER_USER_AGENTS` | Comma-separated custom user agents for scraper rotation |
| `CLAMAV_HOST` | ClamAV daemon hostname (e.g., `clamav`) |
| `CLAMAV_PORT` | ClamAV daemon TCP port (default `3310`) |
| `CLAMAV_SOCKET_PATH` | Unix socket path for ClamAV (alternative to host/port) |

---

## Methodologies Supported

| Standard | Methodology | Status |
|----------|-------------|--------|
| Gold Standard | TPDDTEC v4 (Improved Cookstoves) | ✅ Full validation rules |
| Verra | VM0050 (Metered Energy Cooking) | ✅ Full validation rules |
| Verra | VMR0006 (Retroactive LPG) | ✅ Full validation rules |
| UNFCCC | AMS-II.G (Efficient Cookstoves) | ✅ Full validation rules |

---

## Contributing

This is a proprietary project. For access inquiries, contact the repository owner.

---

## License

Proprietary — All rights reserved.
