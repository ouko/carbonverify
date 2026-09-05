# Agent Context — CarbonVerify

This file provides context for AI coding agents working on the CarbonVerify codebase.

---

## Project Overview

CarbonVerify is a carbon credit MRV (Measurement, Reporting, Verification) platform with two main product surfaces:

1. **Main App** — Project management, data ingestion, emissions calculations, report generation, VVB liaison
2. **Command Center** — Operations dashboard for human review, quality metrics, VVB pipeline, agent performance

It also includes a **Lead Intelligence Engine** that scrapes carbon registries (Verra, Gold Standard, CDM) to identify and score potential clients.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, React Query v5, Zustand, React Router v6, Recharts, Lucide |
| **Backend** | FastAPI, Python 3.11, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, Celery |
| **Database** | PostgreSQL 15 |
| **Cache/Queue** | Redis |
| **Scraping** | Playwright (Chromium), playwright-stealth, BeautifulSoup4, lxml |
| **PDF** | WeasyPrint |
| **Virus Scan** | ClamAV (docker-compose) |
| **DevOps** | Docker Compose, Kubernetes manifests, GitHub Actions CI/CD |
| **Backup** | K8s CronJob + S3, `scripts/backup-db.sh` |
| **Load Testing** | k6 (auth stress, API soak, upload tests) |
| **Secrets** | JWT dual-secret rotation, field-level encryption key rotation |
| **Compliance** | SOC2 controls mapping, security audit checklist, GDPR erasure |
| **Deployment** | Docker Compose production stack (`docker-compose.production.yml`) or Kubernetes (`infrastructure/k8s/`) — see `docs/DEPLOYMENT.md` and `infrastructure/docs/DEPLOYMENT.md` |

---

## Directory Structure

```
carbonverify/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry
│   │   ├── models.py               # SQLAlchemy ORM (User, Project, Lead, ScraperRun, ...)
│   │   ├── schemas.py              # Pydantic schemas
│   │   ├── database.py             # Async engine + session factory
│   │   ├── config.py               # Pydantic settings
│   │   ├── api/
│   │   │   ├── leads.py            # Lead Intelligence REST API
│   │   │   └── ...                 # Other route modules
│   │   ├── auth/                   # JWT, bcrypt, RBAC middleware
│   │   ├── calculations/           # Emissions calculation engine
│   │   ├── services/
│   │   │   └── lead_intelligence/  # Scrapers + scoring
│   │   ├── reports/                # Jinja2 + WeasyPrint
│   │   ├── tasks/                  # Celery tasks
│   │   ├── validation_engine/      # Workflow Validation Engine (orchestrator, proofs, synthetic actors, remediation)
│   │   └── vvb_liaison/            # Registry clients
│   ├── alembic/                    # DB migrations
│   └── tests/                      # pytest suite (~318 tests)
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # Router config
│   │   ├── main.tsx                # Entry point (BrowserRouter)
│   │   ├── components/
│   │   │   ├── Layout.tsx          # Main app shell (sidebar)
│   │   │   └── CommandLayout.tsx   # Command Center shell
│   │   ├── pages/
│   │   │   ├── LeadsPage.tsx       # Lead Intelligence UI
│   │   │   └── command/            # Command Center pages
│   │   ├── hooks/
│   │   │   └── useLeads.ts         # React Query hooks for leads
│   │   ├── services/
│   │   │   └── api.ts              # Axios client with auto-refresh
│   │   ├── stores/
│   │   │   ├── authStore.ts        # Zustand auth (JWT + user)
│   │   │   └── themeStore.ts       # Zustand dark/light mode
│   │   └── types/                  # Shared TypeScript types
│   └── ...
├── infrastructure/
│   └── docs/DEPLOYMENT.md
├── docs/PENETRATION_TESTING.md
├── README.md
├── ARCHITECTURE.md
└── AGENTS.md                       # This file
```

---

## Coding Conventions

### Backend (Python)

- **Async everywhere**: Use `async`/`await` for DB operations, API handlers, external calls
- **SQLAlchemy 2.0 style**: `Mapped[type] = mapped_column(...)` with type hints
- **Pydantic v2**: Use `model_validate`, `model_dump`, not deprecated v1 methods
- **Router pattern**: Each domain has its own `api/{domain}.py` router, included in `main.py`
- **RBAC**: Use `Depends(require_viewer)` / `require_operator` / `require_admin` from `auth/rbac.py`, or `require_permission("users:read")` for granular checks. API key auth uses `get_current_user_or_api_key` which checks `user._api_key_scopes`
- **Celery tasks**: Place in `tasks/{domain}_jobs.py`, include in `celery_app.py` `include` list
- **Tests**: Use `pytest-asyncio`, `AsyncClient` from `httpx`, fixtures in `conftest.py`. Current count: ~318 tests

### Frontend (TypeScript / React)

- **Functional components** with hooks
- **React Query v5**: `useQuery({ queryKey: ['key'], queryFn: async () => {...} })`
- **Zustand**: Simple stores with selectors: `useAuthStore((s) => s.user)`
- **Tailwind**: Utility-first; dark mode via `dark:` prefix
- **Lucide icons**: Import from `lucide-react`
- **Routing**: React Router v6; use `future` flags on `BrowserRouter`
- **API errors**: Let Axios interceptor handle 401 (redirects to `/login`); don't silently swallow errors

### UI Patterns

- **Cards**: `className="card"` for content panels
- **Buttons**: `btn-primary`, `btn-secondary`, `btn-ghost` utility classes
- **Badges**: `badge-slate`, `badge-blue`, `badge-amber`, `badge-red`, `badge-green`
- **Forms**: `input-modern`, `select-modern` for inputs
- **Tables**: `w-full text-sm` with `border-b` rows

---

## Key Architectural Decisions

### Persistent Playwright Browser

The scraper system launches Chromium **once** via a singleton in `playwright_utils.py`:

```python
_browser_instance = None  # Shared across all scrapes
_browser_lock = threading.Lock()

def _launch_browser(headless=False) -> Browser:
    with _browser_lock:
        if _browser_instance:
            return _browser_instance
        # ... launch playwright, start browser
```

- First scrape: ~36s (launch + page load)
- Subsequent: ~18s (reuse)
- CDM locally: non-headless bypasses Incapsula
- Production: `SCRAPER_FORCE_HEADLESS=true` enforces headless; use `PROXY_URL` for IP rotation
- User-agent rotation via `_pick_user_agent()` (5 default agents, override with `SCRAPER_USER_AGENTS`)
- Retry logic with exponential backoff (3x) in `playwright_fetch()`
- `close_persistent_browser()` for cleanup

### Scraper Fallback Behavior

All scrapers attempt **live** first. If empty/error, they fall back to **demo data**:

```python
projects = self._try_live_scrape(...) or self._get_demo_data()
```

The `data_source` field tracks which mode succeeded (`"live"` or `"demo"`).

### Auth Token Handling

- Access token: 15 min expiry, stored in memory (Zustand)
- Refresh token: 7 day expiry, stored in httpOnly cookie
- Axios interceptor: on 401, attempts refresh; on refresh failure, redirects to `/login`
- **Do not** wrap API calls in `try/catch` that swallows errors — let the interceptor work

### Searchable Encrypted Fields

PII columns (e.g., `User.email`) are encrypted with non-deterministic Fernet. To enable exact-match queries (login, uniqueness), a deterministic HMAC-SHA256 hash is stored alongside the ciphertext:

```python
email_hash = compute_searchable_hash(email)
```

- Never query the encrypted column directly for equality.
- `compute_searchable_hash()` uses the same `ENCRYPTION_KEY_HEX` as the Fernet layer.
- Falls back to raw SHA-256 only if no key is configured (development).

### Workflow Validation Engine

The `app/validation_engine/` package provides an enterprise-grade autonomous QA system:

- **State machine**: `PENDING → QUEUED → RUNNING → STEP_VALIDATING → PROOF_GENERATING → REMEDIATION_CHECKING → COMPLETED/FAILED → ARCHIVED`
- **JSON-defined workflows**: Workflow graphs stored in `validation_workflows.workflow_graph` (PostgreSQL JSONB), validated by Pydantic schemas
- **Proof generation**: Every step produces a SHA-256 hashed proof artifact. Proofs are assembled into a Merkle tree per run; the root is anchored to the Radix ledger within 5 minutes
- **Synthetic actors**: `SyntheticActorFactory` creates identifiable test personas (user, admin, service, external_system, browser) with traceable markers injected into HTTP headers, DOM attributes, and phone numbers
- **Auto-remediation**: Pattern-based failure recovery — retry with exponential backoff, rollback, skip, patch, circuit break, or escalate
- **Human escalation gates**: `HumanEscalation` records with SLA deadlines, severity scoring, and 4 escalation levels (L1 operator → L2 engineer → L3 architect → Executive). Celery task `check_stalled_escalations` auto-escalates every 15 minutes
- **AI-led evaluation**: `ai_evaluation` step type calls the Kimi API to score workflow artifacts against a configurable `pass_threshold`; produces `ai_evaluation_request` and `ai_evaluation_response` proof artifacts
- **AI application pipeline**: `application_intake`, `document_collection`, and `document_ai_classification` step types power the public applicant intake flow (`/apply` → `POST /applications` → `ai_application_pipeline` workflow template); see `docs/AI_APPLICATION_PIPELINE.md`
- **API endpoints**: All under `/validation/*` — workflows, runs, steps, proofs, certificates, synthetic actors, escalations. Application intake endpoints under `/applications/*`

### Celery Graceful Shutdown

Signal handlers (`worker_process_shutdown`, `worker_shutdown`) in `celery_app.py` call `close_persistent_browser()` to clean up the persistent Playwright browser before worker exit. This prevents resource leaks in containerized environments.

### Route Ordering (Critical)

In FastAPI, **static routes must come before parameterized routes**:

```python
@router.get("/scraper-history")      # ✅ MUST be first
@router.get("/{lead_id}")            # ✅ MUST be second (UUID param)
```

If `/{lead_id}` is first, FastAPI tries to parse `"scraper-history"` as a UUID and fails.

---

## Environment Variables

Key variables in `.env`:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL async connection |
| `REDIS_URL` | Celery broker + cache |
| `SECRET_KEY` | JWT signing |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Celery config |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 |
| `S3_BUCKET_NAME` | File storage |
| `LEAD_SCRAPER_MODE` | `live` or `demo` |
| `PROXY_URL` | HTTP proxy for scraper IP rotation (e.g. `http://proxy:8080`) |
| `SCRAPER_FORCE_HEADLESS` | `true` to force headless in production containers |
| `SCRAPER_USER_AGENTS` | Comma-separated custom user agents for scraper rotation |
| `ENCRYPTION_KEY_HEX` | 32-byte (64 hex character) key for PII field-level encryption. Must be exactly 64 hex chars; generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `IOT_WEBHOOK_API_KEY` | API key for IoT device webhook authentication |
| `IOT_WEBHOOK_SECRET` | Shared secret for HMAC signature verification on IoT webhooks |
| `WHATSAPP_VERIFY_TOKEN` | Meta webhook verification token for WhatsApp bot |
| `WHATSAPP_APP_SECRET` | Meta app secret for webhook signature validation |
| `OAUTH_GOOGLE_CLIENT_ID` / `OAUTH_GOOGLE_CLIENT_SECRET` | Google OAuth credentials |
| `OAUTH_MICROSOFT_CLIENT_ID` / `OAUTH_MICROSOFT_CLIENT_SECRET` | Microsoft OAuth credentials |
| `OAUTH_OKTA_CLIENT_ID` / `OAUTH_OKTA_CLIENT_SECRET` / `OAUTH_OKTA_DOMAIN` | Okta OAuth credentials |
| `AWS_SES_FROM_EMAIL` | From address for transactional emails |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | SMTP fallback for email delivery |
| `SIEM_ENDPOINT` | Splunk HEC or generic SIEM HTTP endpoint for audit log streaming |
| `SIEM_TOKEN` | SIEM authentication token |
| `SIEM_SOURCE` | SIEM source field (default: `carbonverify`) |
| `SIEM_INDEX` | SIEM index field (default: `main`) |
| `CLAMAV_HOST` | ClamAV daemon hostname (e.g., `clamav`) |
| `CLAMAV_PORT` | ClamAV daemon TCP port (default `3310`) |
| `CLAMAV_SOCKET_PATH` | Unix socket path for ClamAV (alternative to TCP) |
| `ENVIRONMENT` | `development` or `production` |

---

## Common Commands

```bash
# Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
alembic revision --autogenerate -m "description"
alembic upgrade head
pytest tests/ -v

# Frontend
cd frontend
npm run dev
npm run build
npm run analyze   # Build + open bundle size visualization (rollup-plugin-visualizer)
npm test

# Full stack
docker-compose up --build

# Backup (Docker Compose)
./scripts/backup-db.sh
S3_BUCKET=my-bucket ./scripts/backup-db.sh
```

---

## Known Issues / Quirks

- **Verra live scraping**: Blocked by Cloudflare. The Angular grid loads via XHR calls that are hard to intercept reliably without deep Playwright scripting. Demo fallback provides realistic Kenya VCS projects.
- **Gold Standard live scraping**: Their public API now requires authentication (`"Can only accept requests of type: authenticated"`). Demo fallback provides realistic projects.
- **CDM scraping**: ✅ Working reliably. Returns real registered projects from Kenya.
- **Vite chunk size**: ✅ Resolved. Code-splitting + manual vendor chunks reduced main entry chunk to ~29KB.
- **React Router v6 → v7**: Future flags enabled in `main.tsx` to suppress console warnings.

## Local Development (Hybrid Mode)

For fastest iteration, run PostgreSQL + Redis in Docker and the backend/frontend directly:

```bash
# One-time setup
./scripts/setup-local.sh

# Start everything
./scripts/start-local.sh

# Check status
./scripts/status-local.sh

# Stop everything
./scripts/stop-local.sh
```

Or start components manually:

```bash
# 1. Start infrastructure
docker-compose -f docker-compose.yml -f docker-compose.local.yml up -d db redis

# 2. Backend (terminal 1)
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 3. Frontend (terminal 2)
cd frontend
npm run dev

# 4. Celery (terminal 3)
cd backend
source .venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat --loglevel=info
```

**CORS fix for local dev:** Do **not** set `VITE_API_URL` in `frontend/.env.local`. Leave it empty (or remove the file) so the Vite dev server proxies API requests to `localhost:8000` via same-origin, avoiding CORS preflight issues. The `vite.config.ts` proxy routes (`/auth`, `/projects`, `/calculations`, etc.) handle this automatically.

**Browser extensions:** MetaMask and some other extensions inject scripts into `localhost` pages that can break API requests with `net::ERR_FAILED`. Use an incognito/private window if you see unexplained network failures.

### Local Development Troubleshooting

- **Port 5432 already allocated / login fails with DB errors**: Another Postgres container (or process) is using `localhost:5432`. `scripts/start-local.sh` and `scripts/setup-local.sh` now detect this up front. Fix by stopping the conflicting container/process, or reconfigure CarbonVerify to use a different host port by editing `docker-compose.local.yml` and `.env.local`.
- **Port 8001 or 5173 already in use**: The startup scripts now refuse to start if the FastAPI or Vite ports are occupied. Run `./scripts/stop-local.sh` first, or stop the other process manually.
- **`ENCRYPTION_KEY_HEX must be exactly 64 hexadecimal characters`**: Field-level encryption and searchable email hashes require a 32-byte key. Generate one with `python3 -c "import secrets; print(secrets.token_hex(32))"` and set it in `.env.local` (and keep `backend/.env` in sync if you run backend commands directly in `backend/`).
- **`Invalid credentials` on first login after setup**: Usually means the demo users were seeded with a different `ENCRYPTION_KEY_HEX` than the one currently loaded. Reset the local DB (`dropdb`/`createdb` inside the `cv-db` container), rerun migrations, and re-seed.

### Demo Data Seeding

After migrations, seed comprehensive demo data:

```bash
cd backend
source .venv/bin/activate
python -m scripts.seed_demo_data
```

**Demo accounts** (password: `DemoPass123!`):
- `admin@carbonverify.demo` — Admin
- `operator@carbonverify.demo` — Operator
- `developer@carbonverify.demo` — Developer
- `viewer@carbonverify.demo` — Viewer
- `buyer@carbonverify.demo` — Buyer
- `seller@carbonverify.demo` — Seller
- `compliance@carbonverify.demo` — Compliance Officer
- `field@carbonverify.demo` — Field Manager

The seed script creates: 6 projects, 20+ data sources, 8+ calculations, 3 reports, 12 review queue items, 34 agent runs, 39 orchestrator events, 43 audit logs, compliance data (breaches, DSRs, consent), brokerage listings/transactions, 25 leads, field data (enumerators, surveys, tickets), and validation engine data.

If re-running the seed script after a partial failure, truncate tables first (the script does not skip existing records and will hit unique constraints on `buyer_profiles.user_id` and `users.email_hash`).
