# Changelog

All notable changes to CarbonVerify are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added
- **AI Pre-Audit Phase 2 — Lead-to-Project Conversion & AI Pre-Audit** — Qualified scraped leads are automatically converted into CarbonVerify projects with fetched registry documents imported as `FileUpload` / `DataSource` records. A default `pre_audit_document_package` validation workflow runs against each converted project using the Kimi API, producing a readiness score and gap report surfaced on the project detail page. Includes `ProjectPreAudit` model, `LeadToProjectConverter`, `PreAuditRunner`, Celery pipeline tasks, `POST /leads/{lead_id}/convert-and-pre-audit`, and `GET /projects/{project_id}/pre-audit`.
- **AI Pre-Audit Phase 1 — Registry Document Discovery** — Scrapers now extract publicly available document links (PDD, monitoring reports, verification reports) from Verra, Gold Standard, and CDM project pages. New `LeadDocument` model, `RegistryDocumentFetcher`, async Celery tasks, and Lead Intelligence UI panel to view and trigger document fetches.
- **Validation Workflow Builder** — Visual UI for creating and editing JSON-defined validation workflows. Includes step palette, live graph preview, per-step config forms for all 11 step types, templates, client-side graph validation, test-run trigger, and run history/proof viewer. Routes: `/validation-workflows`, `/validation-workflows/:id/builder`, `/validation-workflows/:id/runs/:runId?`.
- **AI-led evaluation step in Workflow Validation Engine** — JSON-defined workflows can now include `ai_evaluation` steps that call the Kimi API, score outputs on a 0.0–1.0 scale, and pass/fail based on a configurable `pass_threshold`. Includes Alembic migration for the `workflow_step_type` enum, `AiEvaluationConfig` Pydantic schema, `AiEvaluationExecutor`, `ai_evaluation_request`/`ai_evaluation_response` proof types, and backend tests.
- **Methodology Designer UX improvements** — Non-technical users can now start from sector templates (Cookstoves, Blue Carbon) and use a simple/advanced mode toggle. Added `methodology_templates` table, read-only API, reusable `FormField` components, inline validation, and frontend tests.

### Production Readiness
- **Python runtime pinned to 3.11** — Reverted experimental Python 3.14 target; backend `Dockerfile`, CI workflow, and documentation now use Python 3.11 for stability
- **Backend Dockerfile hardened** — Uses `python:3.11-slim`, adds explicit `CMD`, fixes healthcheck path, and creates a non-root user
- **Frontend Dockerfile and build context fixed** — Dockerfile now builds from the repository root so backend-relative paths resolve correctly; `.dockerignore` excludes build artifacts and dependency caches
- **Production Docker Compose rewritten** — `docker-compose.production.yml` is now a standalone hardened stack with Redis auth/persistence, nginx reverse proxy, resource limits, and no dev mounts
- **Nginx reverse proxy hardened** — `infrastructure/nginx/nginx.conf` proxies all backend routes, serves the SPA fallback, enforces `client_max_body_size 50m`, and adds CSP/HSTS headers
- **Kubernetes manifests corrected** — Added `frontend-deployment.yaml`, fixed `kustomization.yaml`, `network-policy.yaml` DNS/egress rules, `backup-cronjob.yaml` secret references, `ingress.yaml` rate-limit annotations, `hpa.yaml` memory metric, and aligned `celery-beat-deployment.yaml` with the leader-election scheduler
- **Backend reliability hardening** — Global exception handlers, structured JSON logging, proxy-aware rate limiting, fail-closed encryption and webhook security in production, and safe ClamAV/Redis/SIEM degradation paths
- **Frontend hardening** — Authentication only succeeds after `/users/me` validates; API refresh response is validated; role-based route guards enforce `AdminRoute`; admin nav aligned with guards; `SafeHtml` forces `noopener noreferrer`
- **CI/CD hardened** — GitHub Actions use Python 3.11; mypy, safety, and bandit are no longer allowed to fail; security scan uses the production compose stack
- **Environment template sanitized** — `.env.example` stripped of weak defaults and completed with all variables from `config.py`

### Fixed
- **Celery Beat leader election** — `LeaderElectionScheduler` in `app/tasks/beat_scheduler.py` fixed: `self.app.main_name` (non-existent attribute) changed to `self.app.main`. Beat scheduler now acquires Redis lock successfully and processes scheduled tasks.
- **Demo seed script (`scripts/seed_demo_data.py`)** — Multiple runtime failures fixed so the script completes end-to-end:
  - `seed_field_data`, `seed_human_escalations`, and `seed_admin_portfolio` were defined *after* `if __name__ == "__main__"`, causing `NameError` at runtime. Moved all seed functions before the entrypoint block.
  - `SurveyResponse` and `SupportTicket` require `conversation_id` (FK to `whatsapp_conversations`). Added `WhatsAppConversation` creation inside `seed_field_data` and referenced those IDs.
  - `SupportTicket.project_id` is `NOT NULL`; removed the `random.random() > 0.3 else None` branch that violated the constraint.
  - `EscalationLevel` enum values corrected — `low`/`medium`/`high`/`critical` do not exist; the actual enum uses `l1_operator`/`l2_engineer`/`l3_architect`/`executive`. Updated `seed_human_escalations` to use `list(EscalationLevel)`.
  - `human_escalations.run_id` has a FK to `validation_runs.id`; random UUIDs violated the constraint. Added dummy `ValidationWorkflow` + `ValidationRun` creation inside `seed_human_escalations` so escalation records reference real runs.
- **PostgreSQL enum mismatch** — Added missing `in_progress` value to `dsr_status` enum (was in Python `DSRStatusEnum` but absent from DB), preventing `seed_compliance()` from failing with `InvalidTextRepresentationError`.

### Fixed (continued)
- **Validation error handler JSON serialization** — `RequestValidationError` and `ValidationException` handlers in `app/main.py` now recursively convert `bytes` (and other non-JSON values) to JSON-safe types, preventing 500s on malformed form/json payloads
- **Corporate due-diligence access control** — `/corporate/due-diligence/{token_id}` now returns 403 for users without a portfolio or without holding the token; `CorporateService.get_due_diligence_package` raises 404 instead of an unhandled `ValueError`
- **Data source enum validation** — `source_type` is now validated against `SourceTypeEnum` at the API layer, returning 422 instead of a DB 500 on invalid input
- **K8s health probes** — `app-deployment.yaml` liveness/readiness paths aligned with the canonical FastAPI route (`/health/`)
- **Local Redis port mismatch** — `.env.local` and `backend/.env` now point to `localhost:6380` to match `docker-compose.local.yml`
- **Registry client API keys** — `reports.py` registry submission now awaits async client calls and passes `VERRA_API_KEY` / `GOLD_STANDARD_API_KEY`; `.env.example`, `README.md`, and `docs/DEPLOYMENT.md` document the new variables

### Security
- **Protected `/metrics` endpoint** — Now requires admin authentication (was publicly accessible)
- **Rate limiting on sensitive auth endpoints** — Added `@limiter` to MFA setup/verify/confirm/disable, change-password, admin invite, invite accept, OAuth login/callback/link/unlink, and file uploads (previously unprotected from brute-force)
- **Removed login fallback full-table scan** — Legacy email-hash miss no longer loads entire users table; instead queries only active legacy records with `LIMIT 50` and auto-heals missing hashes
- **Added auth requirements to sensitive read endpoints** — `/compliance/consent/{subject_id}`, `/compliance/methodology/current/{name}`, `/tokenization/tokens`, `/tokenization/tokens/{id}`, `/tokenization/marketplace`, `/tokenization/retirements` now require authentication
- **Frontend URL protocol validation** — All `href` attributes rendering API-provided URLs now validate `startsWith('http')` to prevent `javascript:` XSS vectors (`LeadsPage`, `ReportsPage`, `ReportDetailPage`)
- **Request size limit hardening** — Malformed `Content-Length` header no longer crashes with `ValueError`; returns 400 instead
- **WhatsApp webhook signature validation + replay protection** — `POST /whatsapp` now validates `X-Hub-Signature-256` against `WHATSAPP_APP_SECRET` and rejects duplicate signatures within 5 minutes via Redis deduplication
- **IoT webhook hardening** — `POST /webhooks/iot/{project_id}` now supports optional HMAC-SHA256 signature verification (`X-Signature` + `IOT_WEBHOOK_SECRET`) and mandatory replay protection (`X-Request-ID` + Redis dedup); API key remains as base layer
- **SQL wildcard sanitization** — `users.py` and `leads.py` search filters now escape `%` and `_` wildcards and cap input length at 100 chars to prevent wildcard injection
- **Password policy aligned** — All password schemas (`UserCreate`, `UserCreateByAdmin`, `PasswordChangeRequest`) now consistently require minimum 12 characters (was 8 for registration, 12 for password changes)
- **Hardcoded S3 bucket removed** — Upload endpoint now reads `S3_BUCKET_NAME` from config instead of hardcoded string
- **JWT refresh token uniqueness** — Added `jti` (JWT ID) claim to prevent hash collisions when multiple refresh tokens are issued within the same microsecond

### Performance
- **Redis connection pooling** — `health.py` and `admin.py` now reuse the global pooled connection via `app.auth.sessions._get_redis()` instead of creating/closing a new connection per request
- **Batched COUNT queries in admin stats** — `GET /admin/stats` now uses `asyncio.gather()` to parallelize role counts and status breakdowns (was ~10 sequential round-trips)
- **Batched COUNT queries in dashboard stats** — `GET /dashboard/stats` now fully parallelizes all scalar queries with `asyncio.gather()` (was sequential)
- **Event-loop-aware Redis pool** — `_get_redis()` detects event-loop changes and recreates the pool, eliminating the pre-existing `RuntimeError: Event loop is closed` flaky test failures
- **N+1 query elimination in VVB liaison** — `GET /vvb/follow-up-drafts` now batch-loads all projects and calculation runs with `IN` queries instead of per-report round-trips
- **N+1 query elimination in lead scraping** — `POST /leads/scrape` now batch-loads existing leads by `external_id` with a single `IN` query per source instead of one query per raw lead

### Added
- **AI Methodology Designer** — End-to-end wizard for generating registry-aligned draft methodologies for projects that do not fit existing Verra/Gold Standard methodologies. Includes gap analysis, AI-generated methodology draft with quantification scaffold, human review workflow, and Markdown export. Backend: `methodology-generator` router, `MethodologyGeneratorService`, `GeneratedMethodology` model, and Alembic migration. Frontend: `/methodology-designer/:id?` route, wizard components, and React Query hooks. Requires `KIMI_API_KEY` for live AI generation; falls back to a structured placeholder when the key is absent so the UI remains testable.
- **Invite acceptance page** — New `/register?invite={token}` route with `InviteAcceptPage` component for users to create accounts from invite links
- **Database index on `refresh_tokens.token_hash`** — Speeds up every token refresh validation (previously full table scan)
- **Comprehensive audit logging** — All state-changing endpoints across 8 modules now write to `audit_logs`:
  - `projects.py`: create, update, delete
  - `data_sources.py`: create, update, delete
  - `calculations.py`: create, update, delete, run calculation, approve
  - `reports.py`: create, update, delete, generate, quality-check, submit-to-registry, draft clarification
  - `review_queue.py`: create, update, delete
  - `leads.py`: create, update, delete, score, scrape
  - `orchestrator.py`: trigger, resolve review, assign review, run agent
  - `vvb_liaison.py`: poll registry, draft response
- **Server-side pagination on all backend list endpoints** — Every `GET` endpoint returning collections now accepts `skip` and `limit` query parameters with sensible defaults (50–100) and max caps (200–500)
  - Brokerage: `/listings`, `/transactions`
  - Tokenization: `/tokens`, `/marketplace`
  - WhatsApp/Field: `/enumerators`, `/survey-responses`, `/support-tickets`
  - Validation Engine: `/escalations`, `/runs`, `/synthetic-actors`
  - Compliance: `/breach`, `/conflict-of-interest`, `/methodology`
  - Corporate: `/portfolio/holdings`
  - Review Queue: `/review-queue/`
  - Orchestrator: `/review-queue`
  - Uploads: `/projects/{id}/uploads`
  - Users: `/users/`
- **Client-side pagination on all frontend list pages** — Consistent pagination controls (Prev/Next, "Showing X-Y of Z") following the Projects/DataSources pattern
  - ReviewQueuePage (10 per page)
  - BrokeragePage — Marketplace (6 per page), Transactions (10 per page)
  - TokenizationPage — Marketplace (6 per page)
  - CorporateDashboardPage — Project contributions (8 per page)
  - LeadsPage — Table view (10 per page)
  - ComplianceDashboardPage — Already had pagination for all sections
  - FieldDashboardPage — Already had pagination for enumerators
- **Frontend hooks updated** to pass `skip`/`limit` to backend APIs: `useReviewQueue`, `useBrokerageListings`, `useBrokerageTransactions`, `useTokens`, `useMarketplace`, `useBreaches`, `useConflicts`, `useMethodologyVersions`
- **Dashboard stats query optimization** — Parallelized status count queries to reduce load time

### Fixed
- **Slow loading elements** — Root cause was unbounded backend list responses. Fixed by adding server-side pagination to all list endpoints and client-side pagination to all frontend tables.
- **Axios timeout** — Increased from 10s to 30s to prevent timeouts on slower network connections
- **CORS** — Added `192.168.1.97:5173` (network IP) to allowed origins for local dev across devices

### Added
- **Admin System (Phase 1 & 2)** — Full admin dashboard with role-based access control
  - Backend: Granular permission system (`users:read`, `projects:create`, etc.), `PermissionChecker` dependency, `GET /admin/stats`, `GET /admin/sessions`, `GET /admin/permissions`
  - Backend: User CRUD with soft delete (`is_active`), permission grant/revoke, session revocation, force logout
  - Frontend: Admin layout with sidebar, dashboard stats, user management table with search/filter, user detail with permission editor, session management, settings
  - Frontend: `AdminRoute` guard, `RequirePermission` component, admin nav link in main layout (admin-only)
- **Invite Flow** — Secure user provisioning without email service
  - `POST /auth/admin/invite` — admin generates 7-day invite token
  - `POST /auth/invite/accept` — user creates account with token + password
  - Frontend: Generate Invite modal with copy-to-clipboard link
- **Registration Security Fix** — `POST /auth/register` no longer accepts role from client; always creates `viewer` role
- **Password Reset Flow** — `POST /auth/forgot-password` (enumeration-safe, per-email rate limit) + `POST /auth/reset-password` (token hash verification, complexity enforcement, session revocation). Email service with AWS SES primary / SMTP fallback
- **API Keys / M2M Auth** — `POST/GET/DELETE /api-keys/` with scope enforcement. `FlexibleHTTPBearer` supports both `Bearer <jwt>` and `ApiKey <key>` schemes. SHA-256 hashed keys with `cv_` prefix
- **SSO / OAuth** — Google, Microsoft, Okta via Authlib. `GET /auth/oauth/{provider}` + callback, link/unlink accounts. Frontend OAuth buttons + Connected Accounts section
- **MFA Backup Codes** — 10 one-time codes generated on MFA confirm, stored as SHA-256 hashes. Backup codes accepted as alternative to TOTP at login. `POST /auth/mfa/regenerate-backup-codes` endpoint
- **Security Event Emails** — Email notifications sent on MFA enabled, backup codes regenerated, password changed, and account locked
- **SIEM Streaming** — New `app/security/siem_streaming.py` streams audit logs to Splunk HEC or generic HTTP endpoints. Batched async sends with retry. Configured via `SIEM_ENDPOINT`, `SIEM_TOKEN`, `SIEM_SOURCE`, `SIEM_INDEX`
- **Frontend Permission Guards** — `AdminRoute` now checks specific admin permissions (`users:read`, `system:configure`, `audit:read`, etc.) instead of hardcoded `role === 'admin'`. Non-admin users with granted admin permissions can now access the admin UI

### Fixed
- **Critical backend NameError bugs** in `orchestrator.py` (`trigger`/`decision` undefined in log lines) and `validation_engine.py` (`offset` vs `skip`)
- **Frontend-backend type mismatches** causing HTTP 422 errors at runtime:
  - `useSecurity.ts` MFA confirm — backend no longer requires `email`/`password` in `MFAConfirmRequest`
  - `useTokenization.ts` — `useBuyToken` now passes `tonnes_to_buy` query param; `useRetireToken` payload fields aligned with `TokenRetireRequest`; `MintPayload.calculation_run_id` made required
  - `useCorporate.ts` — `ESGReportPayload` fields aligned with `ESGReportConfig` (`reporting_period_start`, `reporting_period_end`, `scope`, `sdgs`)
  - `useDashboardStats.ts` — `useEmissionsTrend` now unpacks `res.data.trend`
  - `useBrokerage.ts` — `MatchResponse` and `GlobalMatchResponse` types aligned with actual backend responses
  - `useCompliance.ts` — `DSR.subject` → `subject_id`, `Breach.sla_ok` → `sla_violated`, `ConflictOfInterest` fields aligned with backend
- **Missing Python dependencies** — Added `playwright==1.44.0`, `playwright-stealth==1.0.6`, `slowapi==0.1.9` to `requirements.txt`

### Added
- **Workflow Validation Engine** — Enterprise-grade autonomous QA system
  - JSON-defined workflow graph schema with Pydantic validation (10 step types: HTTP, DB query, service call, external API, notification, DOM capture, decision gate, wait, parallel, subflow)
  - State machine with 9 states and immutable transition audit trail (SHA-256 chained hashes)
  - Cryptographic proof generation: per-step SHA-256 proofs assembled into a Merkle tree, anchored to Radix ledger
  - Synthetic Actor Factory with 5 actor types, behavioral profiles, and identifiable markers
  - Auto-remediation engine with 6 actions: retry, rollback, skip, escalate, patch, circuit break
  - Human escalation gates with 4 levels, SLA deadlines, and auto-escalation Celery task
  - REST API under `/validation/*` for workflows, runs, proofs, certificates, synthetic actors, and escalations
  - Celery tasks: `execute_validation_run`, `anchor_run_to_radix`, `cleanup_archived_runs`, `check_stalled_escalations`
  - Alembic migration `1e1e69dad168` creating 8 tables and 9 PostgreSQL enums

### Fixed
- **Login failure for existing users** — Users created before the `email_hash` migration could not log in because the login endpoint queried only by `email_hash`. Added a fallback scan of decrypted emails when hash lookup misses, plus a data migration (`ab7db18e2c68`) to backfill `email_hash` for all existing users. Frontend now shows actual API error messages instead of generic "Invalid email or password".

### Security
- **Searchable encrypted fields** — Added `email_hash` (HMAC-SHA256) to the `User` model to enable exact-match lookups on encrypted emails without exposing plaintext. `compute_searchable_hash()` derives a deterministic keyed hash from the encryption key.
- **Password complexity** — Registration now requires 8+ chars with at least one uppercase letter, one digit, and one special character (`@$!%*?&`)
- **Filename sanitization** — Uploaded filenames are sanitized to prevent path traversal and XSS
- **Heuristic malware detection** — Executable and script file types are rejected at upload time (complements ClamAV containerized scanning)
- **DOMPurify** — `SafeHtml` component for safely rendering any user-generated HTML content

### Infrastructure & Reliability
- **Redis timeout hardening** — Added `socket_connect_timeout=5`, `health_check_interval=30`, `retry_on_timeout=True` to Redis clients in health checks (`app/api/health.py`), pub/sub (`app/orchestrator/pubsub.py`), sessions (`app/auth/sessions.py`), and WhatsApp state machine (`app/services/whatsapp/state_machine.py`)
- **Database query timeout** — PostgreSQL `statement_timeout=30000` (30s) to prevent runaway queries
- **ClamAV virus scanning** — `app/services/clamav_scanner.py` with async `scan_buffer()`, graceful fallback if ClamAV is unreachable. Integrated into upload endpoint and Celery processing task. Docker Compose `clamav` service added to dev/staging/production.
- **Celery graceful shutdown** — `worker_process_shutdown` and `worker_shutdown` signal handlers in `celery_app.py` call `close_persistent_browser()` to clean up Playwright resources before worker exit
- **Scraper hardening** — `PROXY_URL` and `SCRAPER_FORCE_HEADLESS` in `Settings`; user-agent rotation with 5 realistic desktop agents; retry logic with exponential backoff (3x) in `playwright_fetch()`
- **WhatsApp config** — `WHATSAPP_VERIFY_TOKEN` moved from `os.environ` to `Settings`; app no longer crashes on import if token is missing
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
- **Deterministic login lookup** — Fixed a critical bug where login attempted exact-match queries on non-deterministic Fernet-encrypted `email` values. Login now queries the deterministic `email_hash` column. Same fix applied to registration duplicate-check.
- **Settings consistency** — Fixed `os.environ` bypass issues in logging (`configure_logging()`) and Playwright utils. Both now read exclusively from `Settings` / `get_settings()` rather than environment variables directly.
- **GDPR erasure fix** — `_erase_household` and `_erase_developer` in `compliance_jobs.py` were broken by encrypted columns; fixed with Python-side filtering and batch limits.
- **Celery retry bug** — `self.retry()` was called from a standalone async function where `self` doesn't exist. Restructured `process_erasure_request` to catch and retry properly.
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
- **Dockerfile** — Uses `python:3.11-slim`, added non-root `appuser` (UID 1000), added `HEALTHCHECK` instruction
- **Security headers** — Removed deprecated `X-XSS-Protection`, added `Permissions-Policy`, added `TrustedHostMiddleware` (skipped in test env)
- **Config validation** — `SECRET_KEY` now requires min 32 chars, removed insecure defaults for `ENVIRONMENT` (was "development"), `S3_BUCKET_NAME`, `DATABASE_URL`, `REDIS_URL`
- **PyPDF2 → pypdf** — Migrated from deprecated PyPDF2 to maintained `pypdf` library
- **Circuit breakers wired** — `@with_circuit_breaker("kimi_api")` on `KimiAPIClient.chat_completion()`, `@with_circuit_breaker("whatsapp_meta")` on `WhatsAppMetaAPI.send_text_message()`
- **Slowapi deprecation fix** — Monkey-patched `asyncio.iscoroutinefunction = inspect.iscoroutinefunction` before slowapi imports to suppress deprecation warnings

### Testing & QA
- **React Router test wrapper** — `renderWithRouter()` utility with v7 future flags (`v7_startTransition`, `v7_relativeSplatPath`) eliminates console warnings in tests
- **Alembic schema drift fixed** — Repaired broken migration `83f9a053933f` (indexes for non-existent tables), generated `c8e8775f56b9` capturing all missing tables, columns, and indexes
- **Test environment** — `conftest.py` sets `ENVIRONMENT=test` to ensure middleware behavior matches test expectations

### Frontend
- **Code-splitting** — All pages except `LoginPage` now use `React.lazy` + `Suspense` for on-demand loading
- **Manual vendor chunks** — Vite splits `react`, `recharts`, `react-query`, and `lucide` into separate chunks
- **Bundle analysis** — Added `rollup-plugin-visualizer`; run `npm run analyze` to generate `dist/stats.html`
- **Bundle size** — Main entry chunk reduced from ~982KB to ~29KB (155KB vendor-react, 90KB vendor-query, 34KB vendor-ui). Total initial JS load ~305KB.
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
- **All tests passing** — 225 backend tests passing (was ~18 failing). Fixed scraper demo mode fixture, Playwright fallback missing `registry_source` field, structured logging keyword argument support, and encrypted field query bugs
- Scraper history display bug — moved last-scraped info from hidden right-aligned column into a full-width card
- Auth error swallowing in `useScraperHistory` — removed silent `try/catch` so 401s bubble to Axios interceptor
- React Router v7 future flag warnings — added `v7_startTransition` and `v7_relativeSplatPath` to `BrowserRouter`
- Login form autocomplete — added `autoComplete="email"` and `autoComplete="current-password"` attributes

### Changed
- Pinned Python runtime to 3.11 for stability
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
