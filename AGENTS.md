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
| **Backend** | FastAPI, Python 3.14, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, Celery |
| **Database** | PostgreSQL 15 |
| **Cache/Queue** | Redis |
| **Scraping** | Playwright (Chromium), playwright-stealth, BeautifulSoup4, lxml |
| **PDF** | WeasyPrint |
| **DevOps** | Docker Compose |

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
│   │   └── vvb_liaison/            # Registry clients
│   ├── alembic/                    # DB migrations
│   └── tests/                      # pytest suite (143 tests)
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
- **RBAC**: Use `Depends(require_viewer)` / `require_operator` / `require_admin` from `auth/rbac.py`
- **Celery tasks**: Place in `tasks/{domain}_jobs.py`, include in `celery_app.py` `include` list
- **Tests**: Use `pytest-asyncio`, `AsyncClient` from `httpx`, fixtures in `conftest.py`

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
- Always non-headless for CDM (bypasses Incapsula)
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

# Full stack
docker-compose up --build
```

---

## Known Issues / Quirks

- **Verra live scraping**: Blocked by Cloudflare. The Angular grid loads via XHR calls that are hard to intercept reliably without deep Playwright scripting. Demo fallback provides realistic Kenya VCS projects.
- **Gold Standard live scraping**: Their public API now requires authentication (`"Can only accept requests of type: authenticated"`). Demo fallback provides realistic projects.
- **CDM scraping**: ✅ Working reliably. Returns real registered projects from Kenya.
- **Vite chunk size**: Production build warns ~980KB JS bundle. Code-splitting recommended but not critical.
- **React Router v6 → v7**: Future flags enabled in `main.tsx` to suppress console warnings.
