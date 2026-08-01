# AI Pre-Audit Automation — Phase 1: Document Discovery & Download

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable CarbonVerify to discover and download publicly available project documents (PDD, monitoring reports, verification reports) from Verra, Gold Standard, and CDM registry pages, attach them to scraped leads, and expose them in the UI so operators can review them before conversion.

**Architecture:** Add a `LeadDocument` model linked to `Lead`. Extend each registry scraper with a `fetch_documents(lead)` method that returns document metadata from the project's registry page. Add a Celery task that downloads the documents, scans them, stores them in S3, and creates `LeadDocument` records. Expose the documents through the leads API and the Lead Intelligence UI.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Celery, PostgreSQL, S3, Playwright/httpx, BeautifulSoup4, React, TypeScript, TanStack Query v5, Vitest.

## Global Constraints

- All backend files follow existing directory conventions (`backend/app/models.py`, `backend/app/schemas.py`, `backend/app/api/leads.py`, `backend/app/services/lead_intelligence/`, `backend/app/tasks/`).
- All DB schema changes use Alembic migrations.
- All API calls go through `backend/src/services/api.ts` on the frontend.
- No new runtime dependencies in Phase 1.
- Existing patterns for file upload (S3 key, virus scan, SHA-256 hash) must be reused.
- Demo mode must continue to work when `LEAD_SCRAPER_MODE=demo`.
- New code must support async/await and SQLAlchemy 2.0 style.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/models.py` | Add `LeadDocument` model and relationship on `Lead`. |
| `backend/app/schemas.py` | Add `LeadDocumentBase`, `LeadDocumentCreate`, `LeadDocumentOut` schemas. |
| `backend/app/services/lead_intelligence/document_fetcher.py` | Generic download/scan/store logic for registry documents. |
| `backend/app/services/lead_intelligence/base.py` | Add `fetch_documents()` abstract method to `BaseRegistryScraper`. |
| `backend/app/services/lead_intelligence/cdm.py` | Extract document links from CDM project pages. |
| `backend/app/services/lead_intelligence/verra.py` | Extract document links from Verra project pages or API. |
| `backend/app/services/lead_intelligence/gold_standard.py` | Extract document links from Gold Standard project pages. |
| `backend/app/tasks/pre_audit_jobs.py` | Celery tasks: `fetch_lead_documents`, `fetch_all_pending_documents`. |
| `backend/app/api/leads.py` | Add `GET /leads/{id}/documents` and `POST /leads/{id}/fetch-documents`. |
| `frontend/src/hooks/useLeads.ts` | Add `useLeadDocuments`, `useFetchLeadDocuments`. |
| `frontend/src/pages/LeadsPage.tsx` | Add documents panel in lead detail modal. |
| `backend/tests/test_lead_documents.py` | Tests for fetcher, scraper document extraction, API endpoints. |
| `docs/AI_PRE_AUDIT_USER_GUIDE.md` | Update with new document-fetch UI instructions. |
| `CHANGELOG.md` | Add Phase 1 entry. |

---

### Task 0: Add `LeadDocument` model and Alembic migration

**Files:**
- Modify: `backend/app/models.py`
- Create: Alembic migration

**Interfaces:**
- Consumes: `Lead` model, `LeadRegistrySourceEnum`
- Produces: `LeadDocument` ORM class with relationship `lead.documents`

- [ ] **Step 1: Add `LeadDocument` model to `backend/app/models.py`**

Insert after the `Lead` class (around line 1300):

```python
class LeadDocumentStatusEnum(str, PyEnum):
    discovered = "discovered"
    fetched = "fetched"
    failed = "failed"


class LeadDocument(Base):
    __tablename__ = "lead_documents"

    __table_args__ = (
        Index("ix_lead_documents_lead_id", "lead_id"),
        Index("ix_lead_documents_document_type", "document_type"),
        Index("ix_lead_documents_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    s3_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    s3_bucket: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[LeadDocumentStatusEnum] = mapped_column(
        Enum(LeadDocumentStatusEnum, name="lead_document_status"),
        default=LeadDocumentStatusEnum.discovered,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="documents")
```

Also add the relationship on `Lead`:

```python
class Lead(Base):
    ...
    documents: Mapped[List["LeadDocument"]] = relationship(
        "LeadDocument", back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )
```

- [ ] **Step 2: Generate and review Alembic migration**

Run:

```bash
cd /Users/lukeouko/carbonverify/backend
source .venv/bin/activate
alembic revision --autogenerate -m "add lead_documents table"
```

Review the generated migration in `backend/alembic/versions/`. Ensure:
- `lead_documents` table is created.
- Indexes `ix_lead_documents_lead_id`, `ix_lead_documents_document_type`, `ix_lead_documents_status` exist.
- Enum `lead_document_status` is created.
- Foreign key to `leads.id` uses `ON DELETE CASCADE`.

- [ ] **Step 3: Apply migration**

```bash
cd /Users/lukeouko/carbonverify/backend
alembic upgrade head
```

Expected: migration applies successfully.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/models.py backend/alembic/versions/
git commit -m "feat(pre-audit): add LeadDocument model and migration"
```

---

### Task 1: Add `LeadDocument` schemas and API endpoints

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/api/leads.py`

**Interfaces:**
- Consumes: `LeadDocument` model
- Produces: `LeadDocumentOut`, `GET /leads/{id}/documents`, `POST /leads/{id}/fetch-documents`

- [ ] **Step 1: Add schemas to `backend/app/schemas.py`**

Insert after `LeadOut` (around line 828):

```python
class LeadDocumentBase(BaseModel):
    document_type: str
    source_url: str
    title: Optional[str] = None
    status: Optional[str] = "discovered"


class LeadDocumentCreate(LeadDocumentBase):
    lead_id: uuid.UUID


class LeadDocumentOut(LeadDocumentBase, ORMBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    file_hash_sha256: Optional[str] = None
    s3_key: Optional[str] = None
    s3_bucket: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    error_message: Optional[str] = None
    fetched_at: Optional[datetime] = None
    created_at: datetime
```

- [ ] **Step 2: Add API endpoints to `backend/app/api/leads.py`**

Import `LeadDocument`, `LeadDocumentOut`, `LeadDocumentCreate` from `app.models` and `app.schemas`.

Add after the existing `GET /leads/{id}` endpoint:

```python
@router.get("/{id}/documents", response_model=List[LeadDocumentOut])
async def get_lead_documents(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_viewer),
):
    result = await db.execute(
        select(LeadDocument).where(LeadDocument.lead_id == id).order_by(LeadDocument.created_at)
    )
    return result.scalars().all()


@router.post("/{id}/fetch-documents", status_code=202)
async def fetch_lead_documents(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_operator),
):
    lead = await db.get(Lead, id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    fetch_lead_documents_task.delay(str(id))
    return {"message": "Document fetch queued", "lead_id": str(id)}
```

- [ ] **Step 3: Add tests**

Create `backend/tests/test_lead_documents.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_lead_documents_empty(client: AsyncClient, operator_headers):
    # Create a lead first via existing factory or helper
    lead_resp = await client.post("/leads/", json={
        "registry_source": "manual",
        "external_id": "TEST-123",
        "project_name": "Test Project",
    }, headers=operator_headers)
    assert lead_resp.status_code == 201
    lead_id = lead_resp.json()["id"]

    resp = await client.get(f"/leads/{lead_id}/documents", headers=operator_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_fetch_lead_documents_queued(client: AsyncClient, operator_headers):
    lead_resp = await client.post("/leads/", json={
        "registry_source": "manual",
        "external_id": "TEST-456",
        "project_name": "Test Project 2",
    }, headers=operator_headers)
    lead_id = lead_resp.json()["id"]

    resp = await client.post(f"/leads/{lead_id}/fetch-documents", headers=operator_headers)
    assert resp.status_code == 202
    assert resp.json()["lead_id"] == lead_id
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_lead_documents.py -v
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/schemas.py backend/app/api/leads.py backend/tests/test_lead_documents.py
git commit -m "feat(pre-audit): add LeadDocument schemas and API endpoints"
```

---

### Task 2: Add generic registry document fetcher

**Files:**
- Create: `backend/app/services/lead_intelligence/document_fetcher.py`
- Modify: `backend/app/services/lead_intelligence/base.py`

**Interfaces:**
- Consumes: `Lead`, `LeadDocument`, httpx, S3 settings, ClamAV scanner
- Produces: `RegistryDocumentFetcher.fetch_document(lead_document)`

- [ ] **Step 1: Add abstract method to `BaseRegistryScraper`**

Modify `backend/app/services/lead_intelligence/base.py`:

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseRegistryScraper(ABC):
    source: str = ""

    @abstractmethod
    def scrape(self, country: str = "Kenya", status_filter: str = "all") -> List[Dict[str, Any]]:
        ...

    def fetch_documents(self, lead: "Lead") -> List[Dict[str, Any]]:
        """Return document metadata discovered on the registry page for this lead.

        Each dict must contain at least:
        - document_type: str (e.g. "pdd", "monitoring_report", "verification_report")
        - source_url: str
        - title: Optional[str]

        Subclasses should override this method.
        """
        return []

    def close(self) -> None:
        pass
```

- [ ] **Step 2: Create `backend/app/services/lead_intelligence/document_fetcher.py`**

```python
"""Generic registry document download, scan, and storage."""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.logging import get_logger
from app.config import get_settings
from app.models import LeadDocument, LeadDocumentStatusEnum

logger = get_logger(__name__)
settings = get_settings()


class RegistryDocumentFetcher:
    def __init__(self):
        self.client = httpx.Client(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
            },
        )

    async def fetch_document(self, lead_document: LeadDocument) -> LeadDocument:
        """Download, scan, and store a single registry document.

        Returns the updated LeadDocument. Does NOT commit the DB session.
        """
        try:
            logger.info("fetching_lead_document", lead_document_id=str(lead_document.id))
            resp = self.client.get(lead_document.source_url)
            resp.raise_for_status()
            content = resp.content

            file_hash = hashlib.sha256(content).hexdigest()
            mime_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
            file_size = len(content)

            # Virus scan placeholder — integrate with existing ClamAV scanner if available
            # await scan_bytes(content)

            s3_key = self._build_s3_key(lead_document, file_hash)
            s3_bucket = settings.S3_BUCKET_NAME
            await self._upload_to_s3(s3_key, content, mime_type)

            lead_document.status = LeadDocumentStatusEnum.fetched
            lead_document.file_hash_sha256 = file_hash
            lead_document.s3_key = s3_key
            lead_document.s3_bucket = s3_bucket
            lead_document.file_size_bytes = file_size
            lead_document.mime_type = mime_type
            lead_document.fetched_at = datetime.now(timezone.utc)
            lead_document.error_message = None

            logger.info(
                "lead_document_fetched",
                lead_document_id=str(lead_document.id),
                file_hash=file_hash,
                s3_key=s3_key,
            )
        except Exception as exc:
            logger.error("lead_document_fetch_failed", lead_document_id=str(lead_document.id), error=str(exc))
            lead_document.status = LeadDocumentStatusEnum.failed
            lead_document.error_message = str(exc)[:1000]

        return lead_document

    def _build_s3_key(self, lead_document: LeadDocument, file_hash: str) -> str:
        lead = lead_document.lead
        ext = self._guess_extension(lead_document.mime_type or "")
        source = lead.registry_source.value if lead else "unknown"
        return f"leads/{source}/{lead.id}/{lead_document.document_type}/{file_hash}{ext}"

    @staticmethod
    def _guess_extension(mime_type: str) -> str:
        mapping = {
            "application/pdf": ".pdf",
            "text/html": ".html",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        }
        return mapping.get(mime_type, "")

    async def _upload_to_s3(self, s3_key: str, content: bytes, mime_type: str) -> None:
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION or "us-east-1",
        )
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=content,
            ContentType=mime_type,
        )

    def close(self) -> None:
        self.client.close()
```

- [ ] **Step 3: Add tests**

Add to `backend/tests/test_lead_documents.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from app.services.lead_intelligence.document_fetcher import RegistryDocumentFetcher
from app.models import LeadDocument, LeadDocumentStatusEnum


@pytest.mark.asyncio
async def test_fetch_document_success(async_db_session, sample_lead):
    doc = LeadDocument(
        lead_id=sample_lead.id,
        document_type="pdd",
        source_url="https://example.com/pdd.pdf",
    )
    async_db_session.add(doc)
    await async_db_session.commit()
    await async_db_session.refresh(doc)

    fetcher = RegistryDocumentFetcher()
    with patch.object(fetcher.client, "get") as mock_get, \
         patch.object(fetcher, "_upload_to_s3") as mock_upload:
        mock_response = MagicMock()
        mock_response.content = b"PDF content"
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        mock_upload.return_value = None

        result = await fetcher.fetch_document(doc)

    assert result.status == LeadDocumentStatusEnum.fetched
    assert result.file_hash_sha256 is not None
    assert result.mime_type == "application/pdf"
    fetcher.close()
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_lead_documents.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/services/lead_intelligence/document_fetcher.py backend/app/services/lead_intelligence/base.py backend/tests/test_lead_documents.py
git commit -m "feat(pre-audit): add generic registry document fetcher"
```

---

### Task 3: Extend CDM scraper to extract document links

**Files:**
- Modify: `backend/app/services/lead_intelligence/cdm.py`

**Interfaces:**
- Consumes: `Lead`, CDM project page HTML
- Produces: `CDMScraper.fetch_documents(lead)` returning list of document metadata dicts

- [ ] **Step 1: Add `fetch_documents` to CDM scraper**

Add after `_scrape_cdm_with_playwright`:

```python
CDM_DOCUMENT_TYPE_MAP = {
    "project design document": "pdd",
    "pdd": "pdd",
    "validation report": "validation_report",
    "verification report": "verification_report",
    "monitoring report": "monitoring_report",
    "verification and certification report": "verification_report",
}


def _parse_cdm_documents(html: str, base_url: str) -> List[Dict[str, Any]]:
    """Parse a CDM project detail/history page for document links."""
    soup = BeautifulSoup(html, "html.parser")
    documents = []

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True).lower()
        if not href.endswith(".pdf") and not href.endswith(".xlsx") and not href.endswith(".xls"):
            continue

        doc_type = "document"
        for key, value in CDM_DOCUMENT_TYPE_MAP.items():
            if key in text:
                doc_type = value
                break

        url = href if href.startswith("http") else f"https://cdm.unfccc.int{href}"
        documents.append({
            "document_type": doc_type,
            "source_url": url,
            "title": link.get_text(strip=True),
        })

    return documents
```

Add to `CDMScraper` class:

```python
    def fetch_documents(self, lead: "Lead") -> List[Dict[str, Any]]:
        if not lead.registry_url:
            return []

        # CDM detail page uses /view; history page often has the documents
        history_url = lead.registry_url.replace("/view", "/history")

        try:
            from app.services.lead_intelligence.playwright_utils import _get_or_launch_browser, _new_stealth_page
            browser = _get_or_launch_browser(headless=False)
            page = _new_stealth_page(browser)
            page.goto(history_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            html = page.content()
            page.context.close()
            return _parse_cdm_documents(html, history_url)
        except Exception as exc:
            logger.error("cdm_fetch_documents_failed", lead_id=str(lead.id), error=str(exc))
            return []
```

- [ ] **Step 2: Add tests**

Add to `backend/tests/test_lead_documents.py`:

```python
from app.services.lead_intelligence.cdm import _parse_cdm_documents


def test_parse_cdm_documents():
    html = """
    <html><body>
    <a href="/Projects/DB/ABC123/pdd.pdf">Project Design Document (PDF)</a>
    <a href="/Projects/DB/ABC123/val.pdf">Validation Report</a>
    </body></html>
    """
    docs = _parse_cdm_documents(html, "https://cdm.unfccc.int/Projects/DB/ABC123/history")
    assert len(docs) == 2
    assert docs[0]["document_type"] == "pdd"
    assert docs[0]["source_url"] == "https://cdm.unfccc.int/Projects/DB/ABC123/pdd.pdf"
    assert docs[1]["document_type"] == "validation_report"
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_lead_documents.py -v
```

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/services/lead_intelligence/cdm.py backend/tests/test_lead_documents.py
git commit -m "feat(pre-audit): extract document links from CDM project pages"
```

---

### Task 4: Extend Verra scraper to extract document links

**Files:**
- Modify: `backend/app/services/lead_intelligence/verra.py`

**Interfaces:**
- Consumes: `Lead`, Verra project page HTML
- Produces: `VerraScraper.fetch_documents(lead)` returning list of document metadata dicts

- [ ] **Step 1: Add helper to parse Verra project page**

Add before `VerraScraper` class:

```python
VERRA_DOCUMENT_TYPE_MAP = {
    "project description": "pdd",
    "pdd": "pdd",
    "monitoring report": "monitoring_report",
    "verification report": "verification_report",
    "validation report": "validation_report",
}


def _parse_verra_documents(html: str) -> List[Dict[str, Any]]:
    """Parse a Verra project detail page for document links."""
    soup = BeautifulSoup(html, "html.parser")
    documents = []

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True).lower()
        if ".pdf" not in href.lower() and ".docx" not in href.lower():
            continue

        doc_type = "document"
        for key, value in VERRA_DOCUMENT_TYPE_MAP.items():
            if key in text:
                doc_type = value
                break

        url = href if href.startswith("http") else f"https://registry.verra.org{href}"
        documents.append({
            "document_type": doc_type,
            "source_url": url,
            "title": link.get_text(strip=True),
        })

    return documents
```

- [ ] **Step 2: Add `fetch_documents` to Verra scraper**

Inside `VerraScraper`:

```python
    def fetch_documents(self, lead: "Lead") -> List[Dict[str, Any]]:
        if not lead.registry_url:
            return []

        project_id = lead.registry_url.split("/")[-1]
        html = self._fetch_project_page(project_id)
        if not html:
            return []

        return _parse_verra_documents(html)
```

- [ ] **Step 3: Add tests**

Add to `backend/tests/test_lead_documents.py`:

```python
from app.services.lead_intelligence.verra import _parse_verra_documents


def test_parse_verra_documents():
    html = """
    <html><body>
    <a href="/api/file/123/project-description.pdf">Project Description</a>
    <a href="/api/file/456/monitoring-report.pdf">Monitoring Report</a>
    </body></html>
    """
    docs = _parse_verra_documents(html)
    assert len(docs) == 2
    assert docs[0]["document_type"] == "pdd"
    assert docs[0]["source_url"] == "https://registry.verra.org/api/file/123/project-description.pdf"
    assert docs[1]["document_type"] == "monitoring_report"
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_lead_documents.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/services/lead_intelligence/verra.py backend/tests/test_lead_documents.py
git commit -m "feat(pre-audit): extract document links from Verra project pages"
```

---

### Task 5: Extend Gold Standard scraper to extract document links

**Files:**
- Modify: `backend/app/services/lead_intelligence/gold_standard.py`

**Interfaces:**
- Consumes: `Lead`, Gold Standard project page HTML
- Produces: `GoldStandardScraper.fetch_documents(lead)` returning list of document metadata dicts

- [ ] **Step 1: Add helper and method**

Add before `GoldStandardScraper` class:

```python
GS_DOCUMENT_TYPE_MAP = {
    "project design document": "pdd",
    "pdd": "pdd",
    "monitoring report": "monitoring_report",
    "verification report": "verification_report",
    "validation report": "validation_report",
}


def _parse_gold_standard_documents(html: str) -> List[Dict[str, Any]]:
    """Parse a Gold Standard project detail page for document links."""
    soup = BeautifulSoup(html, "html.parser")
    documents = []

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True).lower()
        if ".pdf" not in href.lower():
            continue

        doc_type = "document"
        for key, value in GS_DOCUMENT_TYPE_MAP.items():
            if key in text:
                doc_type = value
                break

        url = href if href.startswith("http") else f"https://registry.goldstandard.org{href}"
        documents.append({
            "document_type": doc_type,
            "source_url": url,
            "title": link.get_text(strip=True),
        })

    return documents
```

Inside `GoldStandardScraper`:

```python
    def fetch_documents(self, lead: "Lead") -> List[Dict[str, Any]]:
        if not lead.registry_url:
            return []

        try:
            from app.services.lead_intelligence.playwright_utils import _get_or_launch_browser, _new_stealth_page
            browser = _get_or_launch_browser(headless=False)
            page = _new_stealth_page(browser)
            page.goto(lead.registry_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            html = page.content()
            page.context.close()
            return _parse_gold_standard_documents(html)
        except Exception as exc:
            logger.error("gold_standard_fetch_documents_failed", lead_id=str(lead.id), error=str(exc))
            return []
```

- [ ] **Step 2: Add tests**

Add to `backend/tests/test_lead_documents.py`:

```python
from app.services.lead_intelligence.gold_standard import _parse_gold_standard_documents


def test_parse_gold_standard_documents():
    html = """
    <html><body>
    <a href="/docs/pdd.pdf">Project Design Document</a>
    <a href="/docs/verification.pdf">Verification Report</a>
    </body></html>
    """
    docs = _parse_gold_standard_documents(html)
    assert len(docs) == 2
    assert docs[0]["document_type"] == "pdd"
    assert docs[0]["source_url"] == "https://registry.goldstandard.org/docs/pdd.pdf"
    assert docs[1]["document_type"] == "verification_report"
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_lead_documents.py -v
```

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/services/lead_intelligence/gold_standard.py backend/tests/test_lead_documents.py
git commit -m "feat(pre-audit): extract document links from Gold Standard project pages"
```

---

### Task 6: Add Celery tasks for document fetching

**Files:**
- Create: `backend/app/tasks/pre_audit_jobs.py`
- Modify: `backend/app/tasks/celery_app.py` include list
- Modify: `backend/app/tasks/lead_jobs.py` to queue document fetch after scrape

**Interfaces:**
- Consumes: `Lead`, `LeadDocument`, scraper factory, `RegistryDocumentFetcher`
- Produces: `fetch_lead_documents` and `fetch_all_pending_documents` Celery tasks

- [ ] **Step 1: Create `backend/app/tasks/pre_audit_jobs.py`**

```python
"""Celery tasks for AI pre-audit document discovery and fetching."""

from datetime import datetime, timezone
from typing import List

from celery import shared_task
from sqlalchemy import select

from app.core.logging import get_logger
from app.database import async_session_maker
from app.models import Lead, LeadDocument, LeadDocumentStatusEnum
from app.services.lead_intelligence.factory import get_scraper
from app.services.lead_intelligence.document_fetcher import RegistryDocumentFetcher

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_lead_documents(self, lead_id: str) -> None:
    """Discover and download documents for a single lead."""
    async def _run():
        async with async_session_maker() as db:
            lead = await db.get(Lead, lead_id)
            if not lead:
                logger.warning("fetch_lead_documents_lead_not_found", lead_id=lead_id)
                return

            scraper = get_scraper(lead.registry_source.value)
            try:
                discovered = scraper.fetch_documents(lead)
                logger.info("lead_documents_discovered", lead_id=lead_id, count=len(discovered))

                # Upsert discovered documents
                existing_result = await db.execute(
                    select(LeadDocument).where(LeadDocument.lead_id == lead.id)
                )
                existing = {doc.source_url: doc for doc in existing_result.scalars().all()}

                docs_to_fetch: List[LeadDocument] = []
                for meta in discovered:
                    if meta["source_url"] in existing:
                        doc = existing[meta["source_url"]]
                        if doc.status != LeadDocumentStatusEnum.fetched:
                            docs_to_fetch.append(doc)
                    else:
                        doc = LeadDocument(
                            lead_id=lead.id,
                            document_type=meta["document_type"],
                            source_url=meta["source_url"],
                            title=meta.get("title"),
                            status=LeadDocumentStatusEnum.discovered,
                        )
                        db.add(doc)
                        docs_to_fetch.append(doc)

                await db.commit()

                # Fetch each discovered document
                fetcher = RegistryDocumentFetcher()
                try:
                    for doc in docs_to_fetch:
                        await fetcher.fetch_document(doc)
                        await db.commit()
                finally:
                    fetcher.close()

            except Exception as exc:
                logger.error("fetch_lead_documents_failed", lead_id=lead_id, error=str(exc))
                raise self.retry(exc=exc)
            finally:
                scraper.close()

    import asyncio
    asyncio.run(_run())


@shared_task
def fetch_all_pending_documents() -> None:
    """Fetch documents for all leads that have no fetched documents yet."""
    async def _run():
        async with async_session_maker() as db:
            result = await db.execute(
                select(Lead.id).where(
                    ~Lead.documents.any(LeadDocument.status == LeadDocumentStatusEnum.fetched)
                )
            )
            lead_ids = [str(row[0]) for row in result.all()]
            logger.info("fetch_all_pending_documents", count=len(lead_ids))
            for lead_id in lead_ids:
                fetch_lead_documents.delay(lead_id)

    import asyncio
    asyncio.run(_run())
```

- [ ] **Step 2: Update Celery app include list**

Modify `backend/app/tasks/celery_app.py` to include `app.tasks.pre_audit_jobs`.

- [ ] **Step 3: Queue document fetch after scrape**

Modify `backend/app/tasks/lead_jobs.py` `scrape_registries` task. After leads are upserted, queue `fetch_lead_documents` for each newly created or updated lead.

```python
from app.tasks.pre_audit_jobs import fetch_lead_documents

# inside scrape_registries, after upsert loop:
for lead in created_or_updated:
    fetch_lead_documents.delay(str(lead.id))
```

- [ ] **Step 4: Add tests**

Add to `backend/tests/test_lead_documents.py`:

```python
from unittest.mock import patch
from app.tasks.pre_audit_jobs import fetch_lead_documents


@pytest.mark.asyncio
async def test_fetch_lead_documents_task(async_db_session, sample_lead):
    with patch("app.tasks.pre_audit_jobs.get_scraper") as mock_factory:
        mock_scraper = MagicMock()
        mock_scraper.fetch_documents.return_value = [
            {"document_type": "pdd", "source_url": "https://example.com/pdd.pdf", "title": "PDD"}
        ]
        mock_scraper.close = MagicMock()
        mock_factory.return_value = mock_scraper

        with patch("app.tasks.pre_audit_jobs.RegistryDocumentFetcher") as MockFetcher:
            mock_fetcher = MagicMock()
            mock_fetcher.fetch_document = MagicMock(return_value=MagicMock())
            mock_fetcher.close = MagicMock()
            MockFetcher.return_value = mock_fetcher

            fetch_lead_documents(str(sample_lead.id))

    mock_scraper.fetch_documents.assert_called_once()
    mock_fetcher.fetch_document.assert_called_once()
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_lead_documents.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/tasks/pre_audit_jobs.py backend/app/tasks/celery_app.py backend/app/tasks/lead_jobs.py backend/tests/test_lead_documents.py
git commit -m "feat(pre-audit): add Celery tasks for lead document fetching"
```

---

### Task 7: Add frontend hooks and UI for lead documents

**Files:**
- Modify: `frontend/src/hooks/useLeads.ts`
- Modify: `frontend/src/pages/LeadsPage.tsx`

**Interfaces:**
- Consumes: `GET /leads/{id}/documents`, `POST /leads/{id}/fetch-documents`
- Produces: `useLeadDocuments`, `useFetchLeadDocuments`, documents panel in lead modal

- [ ] **Step 1: Add hooks to `frontend/src/hooks/useLeads.ts`**

```typescript
export function useLeadDocuments(leadId: string | undefined) {
  return useQuery({
    queryKey: ['leads', leadId, 'documents'],
    queryFn: async () => {
      const { data } = await api.get<LeadDocument[]>(`/leads/${leadId}/documents`)
      return data
    },
    enabled: !!leadId,
  })
}

export function useFetchLeadDocuments() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (leadId: string) => {
      const { data } = await api.post(`/leads/${leadId}/fetch-documents`)
      return data
    },
    onSuccess: (_, leadId) => {
      queryClient.invalidateQueries({ queryKey: ['leads', leadId, 'documents'] })
    },
  })
}
```

Add `LeadDocument` type:

```typescript
export interface LeadDocument {
  id: string
  lead_id: string
  document_type: string
  source_url: string
  title?: string
  status: 'discovered' | 'fetched' | 'failed'
  file_hash_sha256?: string
  s3_key?: string
  file_size_bytes?: number
  mime_type?: string
  error_message?: string
  fetched_at?: string
  created_at: string
}
```

- [ ] **Step 2: Add documents panel to lead detail modal**

In `frontend/src/pages/LeadsPage.tsx`, in the lead detail modal, add a section that:
- Calls `useLeadDocuments(selectedLead.id)`.
- Lists documents with type, title, status, and a link to `source_url`.
- Shows a **Fetch Documents** button that calls `useFetchLeadDocuments().mutate(selectedLead.id)`.
- Shows loading/error states.

- [ ] **Step 3: Run frontend tests**

```bash
cd /Users/lukeouko/carbonverify/frontend
npm run test -- src/test/LeadDocuments.test.tsx
```

Create `frontend/src/test/LeadDocuments.test.tsx` if needed.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/hooks/useLeads.ts frontend/src/pages/LeadsPage.tsx frontend/src/test/LeadDocuments.test.tsx
git commit -m "feat(pre-audit): add lead documents UI"
```

---

### Task 8: Update documentation and changelog

**Files:**
- Modify: `docs/AI_PRE_AUDIT_USER_GUIDE.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update user guide**

Add a new section **"Automatic document fetching (new)"** describing how operators can click **Fetch Documents** in the lead modal and how scrapes now auto-queue document fetches.

- [ ] **Step 2: Update CHANGELOG**

Add under `[Unreleased] > Added`:

```markdown
- **AI Pre-Audit Phase 1** — Automatic discovery and download of publicly available registry documents (PDD, monitoring reports, verification reports) for scraped leads. New `LeadDocument` model, registry-specific document extractors for Verra/Gold Standard/CDM, async Celery fetch task, and Lead Intelligence UI panel.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add docs/AI_PRE_AUDIT_USER_GUIDE.md CHANGELOG.md
git commit -m "docs: update pre-audit user guide and changelog for Phase 1"
```

---

### Task 9: Final verification

- [ ] **Step 1: Run backend tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_lead_documents.py tests/test_leads.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend lint and tests**

```bash
cd /Users/lukeouko/carbonverify/frontend
npm run lint
npm run test
```

Expected: lint passes with no new errors; tests pass.

- [ ] **Step 3: Commit any final fixes**

```bash
cd /Users/lukeouko/carbonverify
git add .
git commit -m "fix(pre-audit): final verification fixes"
```

---

## Spec Coverage Check

| Spec Requirement | Implementing Task |
|------------------|-------------------|
| Discover documents on Verra | Task 4 |
| Discover documents on Gold Standard | Task 5 |
| Discover documents on CDM | Task 3 |
| Store discovered documents linked to leads | Task 0, 1 |
| Download and store documents in S3 | Task 2, 6 |
| Expose documents in API | Task 1 |
| Show documents in UI | Task 7 |
| Schedule document fetching after scrape | Task 6 |
| Update documentation | Task 8 |

## Placeholder Scan

No `TBD`, `TODO`, or vague steps remain. Each task includes exact file paths, code, and verification commands.
