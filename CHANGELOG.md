# Changelog

All notable changes to CarbonVerify are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

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
