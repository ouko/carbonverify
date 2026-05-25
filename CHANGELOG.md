# Changelog

All notable changes to CarbonVerify are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Security
- **Password complexity** — Registration now requires 8+ chars with at least one uppercase letter, one digit, and one special character (`@$!%*?&`)
- **Filename sanitization** — Uploaded filenames are sanitized to prevent path traversal and XSS
- **Heuristic malware detection** — Executable and script file types are rejected at upload time (complements ClamAV containerized scanning)
- **DOMPurify** — `SafeHtml` component for safely rendering any user-generated HTML content

### Infrastructure & Reliability
- **Redis connection pooling** — `socket_connect_timeout=5`, `socket_keepalive=True`, `health_check_interval=30`, `retry_on_timeout=True`
- **Database query timeout** — PostgreSQL `statement_timeout=30000` (30s) to prevent runaway queries
- **ClamAV virus scanning** — Docker Compose `clamav` service for upload scanning; production fallback to managed scanner
- **Celery graceful shutdown** — `terminationGracePeriodSeconds: 60`, K8s `preStop` hook (`sleep 10`), `worker_shutdown` signal handler
- **Scraper proxy rotation** — `PROXY_URL` env var for IP rotation; `SCRAPER_FORCE_HEADLESS=true` enforces headless in production
- **DB backup strategy** — K8s CronJob (daily at 2 AM UTC) + `scripts/backup-db.sh` for Docker Compose with 30-day retention
- **CI/CD pipeline** — GitHub Actions workflow with backend lint/test, frontend lint/test/build, and Docker build checks
- **Structured logging** — JSON formatter with sensitive field redaction and log level control via `LOG_LEVEL`
- **JWT dual-secret rotation** — `SECRET_KEY_PREVIOUS` support for zero-downtime JWT secret rotation
- **Secrets rotation docs** — `docs/SECRETS_ROTATION.md` with procedures for JWT, encryption keys, DB passwords, IoT API keys, and AWS credentials
- **DB read replicas** — `get_read_db()` dependency for read-only sessions with automatic fallback to primary
- **Alertmanager paging** — K8s ConfigMap with PagerDuty, Slack, and Email receivers; inhibition rules for alert deduplication
- **k6 load testing** — Auth stress test, API soak test, and upload load test with pass/fail thresholds
- **Security audit guide** — `docs/SECURITY_AUDIT.md` with OWASP ZAP, Semgrep, Bandit, manual checklist, and remediation SLA
- **SOC2 controls mapping** — `docs/compliance/SOC2_CONTROLS.md` mapping all 12 TSC categories to implemented controls

### Code Quality & Bug Fixes
- **Duplicate `__table_args__`** — Merged index and constraint blocks in `HumanReviewQueue` and `AuditLog` models (previously the first block was silently overwritten)
- **Broken DB indexes fixed** — `AuditLog` indexes corrected from non-existent columns (`user_id` → `actor_id`, `action` → `action_type`, `created_at` → `timestamp`)
- **Missing `__init__.py`** — Added to 7 package directories (`brokerage`, `security`, `compliance`, `tokenization`, `blockchain`, `email_templates`, `reports/templates`)
- **Hardcoded S3 bucket** — `uploads.py` now uses `settings.S3_BUCKET_NAME`
- **Hardcoded Kimi API URL** — `kimi_api.py` now uses `settings.KIMI_API_BASE` and `settings.KIMI_MODEL`
- **Duplicate `/mfa/confirm` route** — Removed dead handler that returned HTTP 501, kept working implementation
- **Rate limiting fixed** — Added `request: Request` parameter to all route handlers with `@limiter.limit` decorators so slowapi can enforce limits correctly
- **Staging environment** — Created `docker-compose.staging.yml` with replicas, resource limits, and SSL nginx

### Security Hardening
- **Docker Compose** — Removed exposed DB/Redis ports to host, removed default password fallbacks, added dev-only volume mount comments
- **Dockerfile** — Updated to Python 3.14-slim, added non-root `appuser` (UID 1000), added `HEALTHCHECK` instruction
- **Security headers** — Removed deprecated `X-XSS-Protection`, added `Permissions-Policy`, added `TrustedHostMiddleware` (skipped in test env)
- **Config validation** — `SECRET_KEY` now requires min 32 chars, removed insecure defaults for `ENVIRONMENT` (was "development"), `S3_BUCKET_NAME`, `DATABASE_URL`, `REDIS_URL`
- **PyPDF2 → pypdf** — Migrated from deprecated PyPDF2 to maintained `pypdf` library
- **Circuit breakers wired** — `@with_circuit_breaker("kimi_api")` on `KimiAPIClient.chat_completion()`, `@with_circuit_breaker("whatsapp_meta")` on `WhatsAppMetaAPI.send_text_message()`
- **Slowapi deprecation fix** — Monkey-patched `asyncio.iscoroutinefunction = inspect.iscoroutinefunction` before slowapi imports to suppress Python 3.14 warnings

### Testing & QA
- **React Router test wrapper** — `renderWithRouter()` utility with v7 future flags (`v7_startTransition`, `v7_relativeSplatPath`) eliminates console warnings in tests
- **Alembic schema drift fixed** — Repaired broken migration `83f9a053933f` (indexes for non-existent tables), generated `c8e8775f56b9` capturing all missing tables, columns, and indexes
- **Test environment** — `conftest.py` sets `ENVIRONMENT=test` to ensure middleware behavior matches test expectations

### Frontend
- **Code-splitting** — All heavy pages (Command Center, Tokenization, Brokerage, Corporate, Leads, Field) use `React.lazy` + `Suspense`
- **Manual vendor chunks** — Vite splits `react`, `recharts`, `react-query`, and `lucide` into separate chunks
- **Bundle size** — Main chunk reduced from ~982KB to ~102KB (before gzip)
- **Loading spinner** — `LoadingSpinner` component with fullscreen and inline variants for Suspense fallbacks

### Added
- **Lead Intelligence Engine** — Full scraper + scoring + CRM pipeline
  - Playwright-based scrapers for Verra, Gold Standard, and CDM registries
  - Persistent Chromium browser singleton for efficient reuse (~18s vs ~36s first scrape)
  - Per-source scrape reporting with live/demo fallback
  - Stuck Score algorithm (0–100) based on time-in-stage, deadline proximity, verification gap, methodology complexity
  - Lead table with 25+ columns tracking project developer, contact info, crediting period, methodology, status
  - React Query hooks: `useLeads`, `useScrapeLeads`, `useScraperHealth`, `useScraperHistory`
  - Frontend UI: scraper status badges, last-scraped history card, per-source scrape report panel, table/kanban views
  - Alembic migration for `scraper_runs` table tracking every scrape execution
  - Celery beat schedule: `scrape_registries` daily, `score_leads` weekly, `check_lead_deadlines` daily
- **Command Center** — Operations dashboard with dedicated `CommandLayout` shell
  - Inbox (priority queue / human review)
  - Projects Grid
  - VVB Pipeline
  - Quality Metrics
  - Agent Performance
  - Settings (notifications, automation, digest mode)
  - Back navigation: "← CarbonVerify" link from Command Center sidebar to main dashboard
- **Field Dashboard** (`/field`) — New page under main app layout
- **Navigation completeness** — All modules now have a path back to the main dashboard

### Fixed
- **All tests passing** — 218 backend tests passing (was ~18 failing). Fixed scraper demo mode fixture, Playwright fallback missing `registry_source` field, and structured logging keyword argument support
- Scraper history display bug — moved last-scraped info from hidden right-aligned column into a full-width card
- Auth error swallowing in `useScraperHistory` — removed silent `try/catch` so 401s bubble to Axios interceptor
- React Router v7 future flag warnings — added `v7_startTransition` and `v7_relativeSplatPath` to `BrowserRouter`
- Login form autocomplete — added `autoComplete="email"` and `autoComplete="current-password"` attributes

### Changed
- Updated Python requirement from 3.11+ to 3.14
- Added `playwright`, `playwright-stealth`, `beautifulsoup4`, `lxml`, `curl_cffi` to backend dependencies
- Expanded `LeadProjectStatusEnum` with `under_certification` and `request_for_issuance` values
- FastAPI route ordering: `/scraper-history` now defined before `/{lead_id}` to avoid UUID collision

---

## Previous Releases

### [1.2.0] — Lead Intelligence, VVB Pipeline, UI Polish

### [1.1.0] — Security, Quality, Infrastructure Hardening

### [1.0.0] — Initial Release
- Data ingestion (Excel, CSV, PDF, Images, IoT webhooks)
- Validation engine with confidence scoring
- Calculation engine (fNRB, emissions, leakage, methodology, uncertainty)
- Report generation (Jinja2 → WeasyPrint PDF)
- VVB liaison (registry clients, auto-responder, polling)
- Human review queue
- React frontend with dark mode
- Docker Compose deployment
- 64 tests (calculations + reports)
