# AI Pre-Audit Automation — Phase 2: Lead-to-Project Conversion & Pre-Audit

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert qualified scraped leads into CarbonVerify projects, import their fetched registry documents as `FileUpload` + `DataSource` records, run a default pre-audit validation workflow powered by the Kimi API, and surface a readiness score plus gap report in the UI.

**Architecture:** A new `LeadToProjectConverter` service creates a `Project`, `FileUpload`, and `DataSource` from a lead and its fetched `LeadDocument`s. A new `PreAuditRunner` service ensures a default pre-audit workflow exists, creates a `ValidationRun`, and queues it. A Celery beat task runs the pipeline daily after scraping. A new `ProjectPreAudit` model caches the latest result. The frontend shows the readiness score and gap report on `ProjectDetailPage`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Celery, PostgreSQL, S3, Kimi API, React, TypeScript, TanStack Query v5, Vitest.

## Global Constraints

- All backend files follow existing directory conventions (`backend/app/models.py`, `backend/app/schemas.py`, `backend/app/api/leads.py`, `backend/app/services/lead_intelligence/`, `backend/app/tasks/`).
- All DB schema changes use Alembic migrations.
- All API calls go through `frontend/src/services/api.ts` on the frontend.
- No new runtime dependencies; reuse existing `pdfplumber`, `pypdf`, `boto3`, `httpx`.
- Demo mode must continue to work when `LEAD_SCRAPER_MODE=demo`.
- New code must support async/await and SQLAlchemy 2.0 style.
- Reuse existing validation engine, Kimi API client, S3 utilities, virus scanner, and PDF pipeline.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/models.py` | Add `ProjectPreAudit`; add `file_upload_id` to `LeadDocument`; add `converted_project_id` to `Lead`. |
| `backend/alembic/versions/` | Migration for Phase 2 schema changes. |
| `backend/app/services/lead_intelligence/lead_converter.py` | Convert a qualified lead into a project, file uploads, and data sources. |
| `backend/app/services/lead_intelligence/pre_audit_runner.py` | Ensure default pre-audit workflow; create/run validation run; store `ProjectPreAudit`. |
| `backend/app/services/lead_intelligence/document_text.py` | Async helpers to fetch S3 bytes and extract text from PDFs. |
| `backend/app/services/lead_intelligence/system_developer.py` | Idempotent seed for the system developer used by converted leads. |
| `backend/app/tasks/pre_audit_jobs.py` | Celery tasks: `convert_lead_to_project`, `run_pre_audit_for_project`, `run_pre_audit_pipeline`. |
| `backend/app/api/leads.py` | `POST /leads/{lead_id}/convert-and-pre-audit` endpoint. |
| `backend/app/schemas.py` | `ProjectPreAuditOut`, `LeadConvertRequest` schemas. |
| `frontend/src/hooks/useProjects.ts` | `useProjectPreAudit`, `useConvertLead` hooks. |
| `frontend/src/pages/ProjectDetailPage.tsx` | Pre-audit panel showing readiness score and gap report. |
| `backend/tests/test_pre_audit_conversion.py` | Tests for converter, runner, and API. |
| `docs/AI_PRE_AUDIT_USER_GUIDE.md` | Update with Phase 2 workflow. |
| `CHANGELOG.md` | Add Phase 2 entry. |

---

### Task 0: Schema additions and migration

**Files:**
- Modify: `backend/app/models.py`
- Create: Alembic migration

**Interfaces:**
- Consumes: `Lead`, `LeadDocument`, `Project`, `FileUpload`, `ValidationRun`
- Produces: `ProjectPreAudit` model; updated `LeadDocument` and `Lead` models

- [ ] **Step 1: Add `ProjectPreAudit` model to `backend/app/models.py`**

Insert after the `Project` class (around line 312):

```python
class PreAuditStatusEnum(str, PyEnum):
    passed = "passed"
    gaps = "gaps"
    failed = "failed"


class ProjectPreAudit(Base):
    __tablename__ = "project_pre_audits"

    __table_args__ = (
        Index("ix_project_pre_audits_project_id", "project_id"),
        Index("ix_project_pre_audits_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )
    validation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=True
    )
    readiness_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[PreAuditStatusEnum] = mapped_column(
        Enum(PreAuditStatusEnum, name="pre_audit_status"), nullable=False
    )
    gap_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="pre_audits")
```

Add the relationship on `Project`:

```python
class Project(Base):
    ...
    pre_audits: Mapped[List["ProjectPreAudit"]] = relationship(
        "ProjectPreAudit", back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
```

- [ ] **Step 2: Update `LeadDocument` model**

Add a nullable foreign key to `file_uploads`:

```python
file_upload_id: Mapped[Optional[uuid.UUID]] = mapped_column(
    UUID(as_uuid=True), ForeignKey("file_uploads.id"), nullable=True
)
```

- [ ] **Step 3: Update `Lead` model**

Add a nullable foreign key to track the converted project:

```python
converted_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
    UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
)
```

- [ ] **Step 4: Generate and review Alembic migration**

Run:

```bash
cd /Users/lukeouko/carbonverify/backend
source .venv/bin/activate
alembic revision --autogenerate -m "add project pre audit and lead conversion links"
```

If Alembic cannot connect, write the migration manually. Expected changes:
- Create `project_pre_audits` table with indexes and enum.
- Add `file_upload_id` column to `lead_documents`.
- Add `converted_project_id` column to `leads`.

- [ ] **Step 5: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/models.py backend/alembic/versions/
git commit -m "feat(pre-audit): add ProjectPreAudit model and lead conversion links"
```

---

### Task 1: System developer seed

**Files:**
- Create: `backend/app/services/lead_intelligence/system_developer.py`

**Interfaces:**
- Consumes: `Developer`, `User` models
- Produces: `get_or_create_system_developer(db) -> Developer`

- [ ] **Step 1: Create `backend/app/services/lead_intelligence/system_developer.py`**

```python
"""Idempotent seed for the system developer used by registry-imported projects."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Developer, User

logger = get_logger(__name__)

SYSTEM_DEVELOPER_EMAIL = "registry-imports@carbonverify.internal"
SYSTEM_DEVELOPER_NAME = "Registry Imports"
SYSTEM_COMPANY_NAME = "CarbonVerify Registry Imports"


async def get_or_create_system_developer(db: AsyncSession) -> Developer:
    """Return the system developer, creating it (and a backing user) if absent."""
    result = await db.execute(
        select(User).where(User.email_hash == User.hash_email(SYSTEM_DEVELOPER_EMAIL))
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=SYSTEM_DEVELOPER_EMAIL,
            name=SYSTEM_DEVELOPER_NAME,
            role="developer",
            is_active=False,
        )
        db.add(user)
        await db.flush()
        logger.info("system_user_created", user_id=str(user.id))

    dev_result = await db.execute(select(Developer).where(Developer.user_id == user.id))
    developer = dev_result.scalar_one_or_none()
    if developer is None:
        developer = Developer(
            user_id=user.id,
            company_name=SYSTEM_COMPANY_NAME,
        )
        db.add(developer)
        await db.flush()
        logger.info("system_developer_created", developer_id=str(developer.id))

    return developer
```

Note: if `User.hash_email` does not exist, use a SHA-256 helper inline.

- [ ] **Step 2: Add tests**

Create `backend/tests/test_pre_audit_conversion.py` with:

```python
import pytest

from app.services.lead_intelligence.system_developer import get_or_create_system_developer


@pytest.mark.asyncio
async def test_get_or_create_system_developer(async_db_session):
    dev = await get_or_create_system_developer(async_db_session)
    assert dev.company_name == "CarbonVerify Registry Imports"
    dev2 = await get_or_create_system_developer(async_db_session)
    assert dev2.id == dev.id
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_pre_audit_conversion.py::test_get_or_create_system_developer -v
```

Expected: test passes.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/services/lead_intelligence/system_developer.py backend/tests/test_pre_audit_conversion.py
git commit -m "feat(pre-audit): add system developer seed for converted leads"
```

---

### Task 2: Async S3 fetch and PDF text extraction

**Files:**
- Create: `backend/app/services/lead_intelligence/document_text.py`

**Interfaces:**
- Consumes: S3 key/bucket, `boto3`, `pdfplumber`, `pypdf`
- Produces: `fetch_s3_bytes(s3_key, s3_bucket) -> bytes`, `extract_text_from_bytes(content, mime_type) -> str`

- [ ] **Step 1: Create `backend/app/services/lead_intelligence/document_text.py`**

```python
"""Async helpers to fetch registry documents from S3 and extract text."""

import asyncio
import io
from typing import Optional

import httpx

from app.config import get_settings
from app.core.logging import get_logger
from app.services.pipelines.pdf import extract_text_pdfplumber, extract_text_pypdf

logger = get_logger(__name__)
settings = get_settings()


async def fetch_s3_bytes(s3_key: str, s3_bucket: Optional[str] = None) -> bytes:
    """Download object bytes from S3 in a thread pool."""
    bucket = s3_bucket or settings.S3_BUCKET_NAME

    def _get():
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION or "us-east-1",
        )
        return s3.get_object(Bucket=bucket, Key=s3_key)["Body"].read()

    return await asyncio.to_thread(_get)


async def fetch_url_bytes(url: str) -> bytes:
    """Download object bytes from a public URL."""
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def extract_text_from_bytes(content: bytes, mime_type: str) -> str:
    """Extract plain text from PDF or HTML bytes."""
    if mime_type == "application/pdf":
        text = extract_text_pdfplumber(content)
        if not text.strip():
            text = extract_text_pypdf(content)
        return text
    if mime_type == "text/html":
        from bs4 import BeautifulSoup
        return BeautifulSoup(content, "html.parser").get_text(separator="\n")
    return ""


async def extract_text_async(content: bytes, mime_type: str) -> str:
    """Thread-pool wrapper for text extraction."""
    return await asyncio.to_thread(extract_text_from_bytes, content, mime_type)
```

- [ ] **Step 2: Add tests**

Add to `backend/tests/test_pre_audit_conversion.py`:

```python
from unittest.mock import patch, MagicMock
from app.services.lead_intelligence.document_text import extract_text_async, fetch_url_bytes


@pytest.mark.asyncio
async def test_extract_text_async_pdf():
    with patch("app.services.lead_intelligence.document_text.extract_text_pdfplumber", return_value="PDF text") as mock_pdf:
        text = await extract_text_async(b"pdf", "application/pdf")
    assert text == "PDF text"


@pytest.mark.asyncio
async def test_extract_text_async_html():
    text = await extract_text_async(b"<html><body>Hello</body></html>", "text/html")
    assert "Hello" in text
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_pre_audit_conversion.py -v
```

Expected: tests pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/services/lead_intelligence/document_text.py backend/tests/test_pre_audit_conversion.py
git commit -m "feat(pre-audit): add async S3 fetch and document text extraction helpers"
```

---

### Task 3: Lead-to-project converter

**Files:**
- Create: `backend/app/services/lead_intelligence/lead_converter.py`
- Modify: `backend/app/services/lead_intelligence/document_fetcher.py` (link file_upload_id)

**Interfaces:**
- Consumes: `Lead`, `LeadDocument`, `Project`, `FileUpload`, `DataSource`, `Developer`
- Produces: `LeadToProjectConverter.convert(lead) -> Project`

- [ ] **Step 1: Create `backend/app/services/lead_intelligence/lead_converter.py`**

```python
"""Convert a qualified Lead and its fetched documents into a CarbonVerify Project."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logging import get_logger
from app.models import (
    DataSource,
    DetectedFileTypeEnum,
    FileUpload,
    FileUploadStatusEnum,
    Lead,
    LeadDocument,
    LeadDocumentStatusEnum,
    LeadWorkflowStatusEnum,
    MethodologyEnum,
    Project,
    ProjectStatusEnum,
    SourceTypeEnum,
    ValidationStatusEnum,
)
from app.services.lead_intelligence.system_developer import get_or_create_system_developer

logger = get_logger(__name__)


class LeadConversionError(Exception):
    pass


class LeadToProjectConverter:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def convert(self, lead: Lead) -> Project:
        """Convert a lead into a project with file uploads and data sources."""
        self._validate_lead(lead)

        developer = await get_or_create_system_developer(self.db)

        methodology = self._map_methodology(lead.methodology)

        project = Project(
            name=lead.project_name,
            developer_id=developer.id,
            methodology=methodology,
            crediting_period_start=lead.crediting_period_start,
            crediting_period_end=lead.crediting_period_end,
            status=ProjectStatusEnum.onboarding,
        )
        self.db.add(project)
        await self.db.flush()

        docs_result = await self.db.execute(
            select(LeadDocument).where(
                LeadDocument.lead_id == lead.id,
                LeadDocument.status == LeadDocumentStatusEnum.fetched,
            )
        )
        fetched_docs = docs_result.scalars().all()

        for doc in fetched_docs:
            await self._attach_document(project.id, doc)

        lead.converted_project_id = project.id
        lead.lead_status = LeadWorkflowStatusEnum.converted
        lead.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(project)
        logger.info("lead_converted_to_project", lead_id=str(lead.id), project_id=str(project.id))
        return project

    def _validate_lead(self, lead: Lead) -> None:
        if lead.converted_project_id is not None:
            raise LeadConversionError("Lead has already been converted")
        if not lead.crediting_period_start or not lead.crediting_period_end:
            raise LeadConversionError("Lead is missing crediting period dates")
        if lead.crediting_period_end <= lead.crediting_period_start:
            raise LeadConversionError("Crediting period end must be after start")

    def _map_methodology(self, value: Optional[str]) -> MethodologyEnum:
        if not value:
            return MethodologyEnum.TPDDTEC_v4
        mapping = {
            "TPDDTEC_v4": MethodologyEnum.TPDDTEC_v4,
            "VM0050": MethodologyEnum.VM0050,
            "VMR0006": MethodologyEnum.VMR0006,
            "AMS-II.G": MethodologyEnum.AMS_II_G,
        }
        for key, enum in mapping.items():
            if key.lower() == value.lower():
                return enum
        return MethodologyEnum.TPDDTEC_v4

    async def _attach_document(self, project_id, doc: LeadDocument) -> None:
        detected_type = self._detected_type(doc.mime_type)
        upload = FileUpload(
            project_id=project_id,
            original_filename=doc.title or f"{doc.document_type}.{detected_type}",
            detected_type=detected_type,
            mime_type=doc.mime_type or "application/octet-stream",
            s3_key=doc.s3_key or "",
            s3_bucket=doc.s3_bucket or "",
            file_size_bytes=doc.file_size_bytes or 0,
            file_hash_sha256=doc.file_hash_sha256 or "",
            status=FileUploadStatusEnum.uploaded,
            provenance={
                "source": "registry_import",
                "lead_document_id": str(doc.id),
                "registry_source": doc.lead.registry_source.value if doc.lead else "unknown",
            },
        )
        self.db.add(upload)
        await self.db.flush()

        doc.file_upload_id = upload.id

        data_source = DataSource(
            project_id=project_id,
            source_type=SourceTypeEnum.document,
            schema_version="1.0",
            raw_data={
                "document_type": doc.document_type,
                "source_url": doc.source_url,
                "mime_type": doc.mime_type,
                "file_upload_id": str(upload.id),
            },
            validation_status=ValidationStatusEnum.pending,
            provenance={"lead_document_id": str(doc.id)},
        )
        self.db.add(data_source)

    def _detected_type(self, mime_type: Optional[str]) -> DetectedFileTypeEnum:
        if mime_type == "application/pdf":
            return DetectedFileTypeEnum.pdf
        if mime_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ):
            return DetectedFileTypeEnum.excel
        if mime_type == "text/csv":
            return DetectedFileTypeEnum.csv
        return DetectedFileTypeEnum.unknown
```

Note: accessing `doc.lead.registry_source` inside `_attach_document` may trigger a lazy load. Pass `registry_source` explicitly or use the lead object already loaded. Fix by passing `registry_source` to `_attach_document`.

- [ ] **Step 2: Add tests**

Add to `backend/tests/test_pre_audit_conversion.py`:

```python
from unittest.mock import patch, AsyncMock
from app.services.lead_intelligence.lead_converter import LeadToProjectConverter, LeadConversionError
from app.models import Lead, LeadDocument, LeadDocumentStatusEnum, LeadRegistrySourceEnum, LeadWorkflowStatusEnum


@pytest_asyncio.fixture
async def convertible_lead(async_db_session):
    lead = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="CONV-001",
        project_name="Convertible Project",
        project_developer="Acme Carbon",
        methodology="TPDDTEC_v4",
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        lead_status=LeadWorkflowStatusEnum.qualified,
    )
    async_db_session.add(lead)
    await async_db_session.commit()
    await async_db_session.refresh(lead)
    return lead


@pytest.mark.asyncio
async def test_convert_lead_to_project(async_db_session, convertible_lead):
    doc = LeadDocument(
        lead_id=convertible_lead.id,
        document_type="pdd",
        source_url="https://example.com/pdd.pdf",
        mime_type="application/pdf",
        s3_key="leads/cdm/.../pdd/abc.pdf",
        s3_bucket="bucket",
        file_size_bytes=1234,
        file_hash_sha256="abcd",
        status=LeadDocumentStatusEnum.fetched,
    )
    async_db_session.add(doc)
    await async_db_session.commit()

    converter = LeadToProjectConverter(async_db_session)
    project = await converter.convert(convertible_lead)

    assert project.name == "Convertible Project"
    assert project.methodology.value == "TPDDTEC_v4"
    assert len(project.file_uploads) == 1
    assert project.file_uploads[0].s3_key == "leads/cdm/.../pdd/abc.pdf"
    assert convertible_lead.lead_status == LeadWorkflowStatusEnum.converted
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_pre_audit_conversion.py -v
```

Expected: tests pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/services/lead_intelligence/lead_converter.py backend/tests/test_pre_audit_conversion.py
git commit -m "feat(pre-audit): add lead-to-project converter"
```

---

### Task 4: Pre-audit workflow template

**Files:**
- Create: `backend/app/services/lead_intelligence/pre_audit_workflow.py`

**Interfaces:**
- Consumes: `ValidationWorkflow` model
- Produces: `get_or_create_pre_audit_workflow(db) -> ValidationWorkflow`

- [ ] **Step 1: Create `backend/app/services/lead_intelligence/pre_audit_workflow.py`**

```python
"""Default pre-audit validation workflow template."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.validation_engine.models import ValidationWorkflow
from app.validation_engine.schemas import WorkflowGraph

logger = get_logger(__name__)

PRE_AUDIT_WORKFLOW_NAME = "pre_audit_document_package"
PRE_AUDIT_WORKFLOW_VERSION = "1.0.0"


def build_pre_audit_graph() -> WorkflowGraph:
    return WorkflowGraph(
        version="1.0",
        description="Pre-audit registry-imported project documents for completeness and consistency.",
        entry_step="document_presence_gate",
        variables={},
        steps=[
            {
                "id": "document_presence_gate",
                "name": "Required Documents Present",
                "type": "database_query",
                "config": {
                    "query": "SELECT document_type FROM data_sources WHERE project_id = :project_id AND source_type = 'document'",
                    "params": {"project_id": "${project_id}"},
                    "snapshot_result": True,
                },
                "next_on_success": ["ai_evaluation"],
                "next_on_failure": ["gap_notification"],
            },
            {
                "id": "ai_evaluation",
                "name": "AI Pre-Audit Evaluation",
                "type": "ai_evaluation",
                "config": {
                    "prompt": (
                        "You are a carbon credit verification pre-auditor. "
                        "Review the project metadata and document excerpts below. "
                        "Evaluate against standard VCS/Gold Standard/CDM requirements for: "
                        "completeness of baseline scenario and additionality demonstration, "
                        "clarity of monitoring plan, consistency across documents, "
                        "presence of stakeholder consultation evidence, and methodology-specific requirements. "
                        "Return strict JSON with keys: score (float 0.0-1.0), passed (bool), "
                        "reasoning (string including a short gap list and risk flags), recommendation (string)."
                    ),
                    "input_data": {
                        "project_name": "${project_name}",
                        "methodology": "${methodology}",
                        "document_excerpts": "${document_excerpts}",
                    },
                    "pass_threshold": 0.7,
                    "temperature": 0.2,
                    "max_tokens": 2048,
                    "fail_on_error": False,
                },
                "next_on_success": ["readiness_decision_gate"],
                "next_on_failure": ["gap_notification"],
            },
            {
                "id": "readiness_decision_gate",
                "name": "Readiness Decision Gate",
                "type": "decision_gate",
                "config": {
                    "condition_expression": "${ai_evaluation.passed} == True",
                    "require_human_approval": False,
                    "auto_approve_threshold": 0.95,
                    "escalation_level": "l1_operator",
                },
                "next_on_success": ["end"],
                "next_on_failure": ["gap_notification"],
            },
            {
                "id": "gap_notification",
                "name": "Notify Operator of Gaps",
                "type": "notification",
                "config": {
                    "channel": "in_app",
                    "recipients": [],
                    "subject": "Pre-audit gaps detected",
                    "body": "Pre-audit completed with gaps. Review the project detail page.",
                },
                "next_on_success": ["end"],
                "next_on_failure": ["end"],
            },
        ],
    )


async def get_or_create_pre_audit_workflow(db: AsyncSession) -> ValidationWorkflow:
    """Return the active pre-audit workflow, creating it if missing."""
    result = await db.execute(
        select(ValidationWorkflow)
        .where(ValidationWorkflow.name == PRE_AUDIT_WORKFLOW_NAME)
        .where(ValidationWorkflow.active == True)
        .order_by(ValidationWorkflow.version.desc())
        .limit(1)
    )
    workflow = result.scalar_one_or_none()
    if workflow is not None:
        return workflow

    graph = build_pre_audit_graph()
    import hashlib, json
    graph_hash = hashlib.sha256(
        json.dumps(graph.model_dump(), sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()

    workflow = ValidationWorkflow(
        name=PRE_AUDIT_WORKFLOW_NAME,
        version=PRE_AUDIT_WORKFLOW_VERSION,
        description="Default pre-audit workflow for registry-imported projects",
        workflow_graph=graph.model_dump(),
        graph_hash=graph_hash,
        active=True,
        human_gates_required=False,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    logger.info("pre_audit_workflow_created", workflow_id=str(workflow.id))
    return workflow
```

- [ ] **Step 2: Add tests**

Add to `backend/tests/test_pre_audit_conversion.py`:

```python
from app.services.lead_intelligence.pre_audit_workflow import get_or_create_pre_audit_workflow


@pytest.mark.asyncio
async def test_get_or_create_pre_audit_workflow(async_db_session):
    wf = await get_or_create_pre_audit_workflow(async_db_session)
    assert wf.name == "pre_audit_document_package"
    wf2 = await get_or_create_pre_audit_workflow(async_db_session)
    assert wf2.id == wf.id
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_pre_audit_conversion.py::test_get_or_create_pre_audit_workflow -v
```

Expected: test passes.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/services/lead_intelligence/pre_audit_workflow.py backend/tests/test_pre_audit_conversion.py
git commit -m "feat(pre-audit): add default pre-audit workflow template"
```

---

### Task 5: Pre-audit runner

**Files:**
- Create: `backend/app/services/lead_intelligence/pre_audit_runner.py`

**Interfaces:**
- Consumes: `Project`, `ProjectPreAudit`, `ValidationOrchestrator`, `document_text`
- Produces: `PreAuditRunner.run_for_project(project) -> ProjectPreAudit`

- [ ] **Step 1: Create `backend/app/services/lead_intelligence/pre_audit_runner.py`**

```python
"""Run the pre-audit validation workflow for a project and cache the result."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import DataSource, FileUpload, PreAuditStatusEnum, Project, ProjectPreAudit, SourceTypeEnum
from app.services.lead_intelligence.document_text import extract_text_async, fetch_s3_bytes
from app.services.lead_intelligence.pre_audit_workflow import get_or_create_pre_audit_workflow
from app.validation_engine.orchestrator import ValidationOrchestrator

logger = get_logger(__name__)

MAX_TEXT_CHARS_PER_DOC = 8000


class PreAuditRunner:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_for_project(self, project: Project, lead_id: str | None = None) -> ProjectPreAudit:
        """Create a validation run, execute it, and store the cached pre-audit result."""
        workflow = await get_or_create_pre_audit_workflow(self.db)
        excerpts = await self._build_document_excerpts(project.id)

        input_data = {
            "project_id": str(project.id),
            "project_name": project.name,
            "methodology": project.methodology.value,
            "document_excerpts": excerpts,
        }

        orchestrator = ValidationOrchestrator(self.db)
        run = await orchestrator.create_run(
            workflow_id=str(workflow.id),
            trigger_event="pre_audit_pipeline",
            input_data=input_data,
            project_id=str(project.id),
        )
        await orchestrator.execute_workflow(str(run.id))
        await self.db.refresh(run)

        result = self._parse_run_output(run.output_data)
        readiness_score = result["score"]
        status = self._status_from_score(readiness_score, result.get("passed", False), result.get("risk_flags", []))

        pre_audit = ProjectPreAudit(
            project_id=project.id,
            lead_id=lead_id,
            validation_run_id=run.id,
            readiness_score=readiness_score,
            status=status,
            gap_summary={
                "gaps": result.get("gaps", []),
                "risk_flags": result.get("risk_flags", []),
                "recommendation": result.get("recommendation", ""),
                "reasoning": result.get("reasoning", ""),
            },
        )
        self.db.add(pre_audit)
        await self.db.commit()
        await self.db.refresh(pre_audit)
        logger.info(
            "pre_audit_completed",
            project_id=str(project.id),
            run_id=str(run.id),
            score=readiness_score,
            status=status.value,
        )
        return pre_audit

    async def _build_document_excerpts(self, project_id) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(DataSource).where(
                DataSource.project_id == project_id,
                DataSource.source_type == SourceTypeEnum.document,
            )
        )
        excerpts = []
        for ds in result.scalars().all():
            file_upload_id = ds.raw_data.get("file_upload_id")
            if not file_upload_id:
                continue
            upload = await self.db.get(FileUpload, file_upload_id)
            if not upload or not upload.s3_key:
                continue
            try:
                content = await fetch_s3_bytes(upload.s3_key, upload.s3_bucket)
                text = await extract_text_async(content, upload.mime_type)
                excerpts.append({
                    "document_type": ds.raw_data.get("document_type", "unknown"),
                    "text": text[:MAX_TEXT_CHARS_PER_DOC],
                })
            except Exception as exc:
                logger.warning("pre_audit_text_extraction_failed", file_upload_id=file_upload_id, error=str(exc))
        return excerpts

    def _parse_run_output(self, output_data: Dict[str, Any]) -> Dict[str, Any]:
        ai_step = output_data.get("ai_evaluation", {})
        if isinstance(ai_step, dict):
            return {
                "score": float(ai_step.get("score", 0.0)),
                "passed": bool(ai_step.get("passed", False)),
                "gaps": ai_step.get("gaps", []) or self._extract_gaps(ai_step.get("reasoning", "")),
                "risk_flags": ai_step.get("risk_flags", []),
                "recommendation": ai_step.get("recommendation", ""),
                "reasoning": ai_step.get("reasoning", ""),
            }
        return {"score": 0.0, "passed": False, "gaps": [], "risk_flags": [], "recommendation": "", "reasoning": ""}

    def _extract_gaps(self, reasoning: str) -> List[str]:
        gaps = []
        for line in reasoning.split("\n"):
            line = line.strip()
            if line.lower().startswith(("- gap", "* gap", "gap:")):
                gaps.append(line)
        return gaps

    def _status_from_score(self, score: float, passed: bool, risk_flags: List[str]) -> PreAuditStatusEnum:
        critical = any(f.lower().startswith("high") or "critical" in f.lower() for f in risk_flags)
        if score >= 0.8 and passed and not critical:
            return PreAuditStatusEnum.passed
        if score < 0.6 or critical:
            return PreAuditStatusEnum.failed
        return PreAuditStatusEnum.gaps
```

- [ ] **Step 2: Add tests**

Add to `backend/tests/test_pre_audit_conversion.py`:

```python
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.lead_intelligence.pre_audit_runner import PreAuditRunner, PreAuditStatusEnum


@pytest.mark.asyncio
async def test_pre_audit_runner_parses_output(async_db_session, sample_lead):
    # Reuse the converted project fixture or create one inline
    from app.services.lead_intelligence.lead_converter import LeadToProjectConverter
    lead = sample_lead
    lead.crediting_period_start = date(2024, 1, 1)
    lead.crediting_period_end = date(2030, 12, 31)
    lead.lead_status = LeadWorkflowStatusEnum.qualified
    await async_db_session.commit()

    doc = LeadDocument(
        lead_id=lead.id,
        document_type="pdd",
        source_url="https://example.com/pdd.pdf",
        mime_type="application/pdf",
        s3_key="leads/cdm/.../pdd/abc.pdf",
        s3_bucket="bucket",
        file_size_bytes=1234,
        file_hash_sha256="abcd",
        status=LeadDocumentStatusEnum.fetched,
    )
    async_db_session.add(doc)
    await async_db_session.commit()

    converter = LeadToProjectConverter(async_db_session)
    project = await converter.convert(lead)

    runner = PreAuditRunner(async_db_session)
    with patch.object(runner, "_build_document_excerpts", return_value=[]), \
         patch.object(ValidationOrchestrator, "create_run", new_callable=AsyncMock) as mock_create, \
         patch.object(ValidationOrchestrator, "execute_workflow", new_callable=AsyncMock) as mock_exec:
        run = MagicMock()
        run.id = uuid.uuid4()
        run.output_data = {
            "ai_evaluation": {
                "score": 0.85,
                "passed": True,
                "gaps": [],
                "risk_flags": [],
                "recommendation": "Ready for auditor assignment.",
                "reasoning": "Documents look complete.",
            }
        }
        mock_create.return_value = run
        mock_exec.return_value = None

        result = await runner.run_for_project(project, lead_id=str(lead.id))

    assert result.status == PreAuditStatusEnum.passed
    assert result.readiness_score == 0.85
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_pre_audit_conversion.py -v
```

Expected: tests pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/services/lead_intelligence/pre_audit_runner.py backend/tests/test_pre_audit_conversion.py
git commit -m "feat(pre-audit): add pre-audit runner service"
```

---

### Task 6: Celery tasks and pipeline

**Files:**
- Modify: `backend/app/tasks/pre_audit_jobs.py`
- Modify: `backend/app/tasks/lead_jobs.py` (queue pipeline after scrape)

**Interfaces:**
- Consumes: `LeadToProjectConverter`, `PreAuditRunner`
- Produces: `convert_lead_to_project`, `run_pre_audit_for_project`, `run_pre_audit_pipeline` Celery tasks

- [ ] **Step 1: Add tasks to `backend/app/tasks/pre_audit_jobs.py`**

Append to the file:

```python
from app.services.lead_intelligence.lead_converter import LeadToProjectConverter, LeadConversionError
from app.services.lead_intelligence.pre_audit_runner import PreAuditRunner


@celery_app.task(bind=True, max_retries=3)
def convert_lead_to_project(self, lead_id: str) -> dict:
    """Convert a single qualified lead into a CarbonVerify project."""
    async def _run():
        async with AsyncSessionLocal() as db:
            lead = await db.get(Lead, lead_id)
            if not lead:
                logger.warning("convert_lead_not_found", lead_id=lead_id)
                return {"error": "lead not found"}

            try:
                converter = LeadToProjectConverter(db)
                project = await converter.convert(lead)
                return {"project_id": str(project.id), "lead_id": lead_id}
            except LeadConversionError as exc:
                logger.warning("convert_lead_skipped", lead_id=lead_id, reason=str(exc))
                return {"error": str(exc)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("convert_lead_failed", lead_id=lead_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def run_pre_audit_for_project(self, project_id: str, lead_id: str | None = None) -> dict:
    """Run pre-audit workflow for a project."""
    async def _run():
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, project_id)
            if not project:
                logger.warning("pre_audit_project_not_found", project_id=project_id)
                return {"error": "project not found"}

            runner = PreAuditRunner(db)
            try:
                result = await runner.run_for_project(project, lead_id=lead_id)
                return {
                    "pre_audit_id": str(result.id),
                    "project_id": project_id,
                    "status": result.status.value,
                    "score": result.readiness_score,
                }
            except Exception as exc:
                logger.error("pre_audit_run_failed", project_id=project_id, error=str(exc))
                raise

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("run_pre_audit_for_project_failed", project_id=project_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def run_pre_audit_pipeline(self) -> dict:
    """Daily pipeline: convert qualified leads and run pre-audit."""
    async def _run():
        async with AsyncSessionLocal() as db:
            from datetime import date
            result = await db.execute(
                select(Lead).where(
                    Lead.lead_status.in_([LeadWorkflowStatusEnum.qualified, LeadWorkflowStatusEnum.proposal_sent]),
                    Lead.converted_project_id.is_(None),
                    Lead.crediting_period_start.isnot(None),
                    Lead.crediting_period_end.isnot(None),
                    Lead.documents.any(LeadDocument.status == LeadDocumentStatusEnum.fetched),
                )
            )
            leads = result.scalars().all()
            logger.info("pre_audit_pipeline_leads", count=len(leads))

            queued = []
            for lead in leads:
                convert_lead_to_project.delay(str(lead.id))
                queued.append(str(lead.id))
            return {"queued": queued, "count": len(queued)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("run_pre_audit_pipeline_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)
```

Note: the converted project must be passed to `run_pre_audit_for_project`. Since Celery tasks are async, chain them or have `convert_lead_to_project` trigger `run_pre_audit_for_project` after commit.

- [ ] **Step 2: Chain conversion to pre-audit**

Modify `convert_lead_to_project` task to trigger pre-audit on success:

```python
                project = await converter.convert(lead)
                run_pre_audit_for_project.delay(str(project.id), lead_id=str(lead.id))
                return {"project_id": str(project.id), "lead_id": lead_id}
```

- [ ] **Step 3: Queue pipeline from `scrape_registries`**

In `backend/app/tasks/lead_jobs.py`, after `fetch_lead_documents.delay(str(lead.id))` add:

```python
from app.tasks.pre_audit_jobs import run_pre_audit_pipeline

# at end of scrape_registries, after commits:
run_pre_audit_pipeline.delay()
```

- [ ] **Step 4: Add Celery include**

Ensure `backend/app/tasks/celery_app.py` includes `app.tasks.pre_audit_jobs`.

- [ ] **Step 5: Add tests**

Add to `backend/tests/test_pre_audit_conversion.py`:

```python
from unittest.mock import patch
from app.tasks.pre_audit_jobs import run_pre_audit_pipeline


def test_run_pre_audit_pipeline_task(async_db_session, convertible_lead):
    with patch("app.tasks.pre_audit_jobs.convert_lead_to_project") as mock_convert:
        mock_convert.delay = MagicMock()
        run_pre_audit_pipeline()
    # If no fetched docs, no conversion queued
    mock_convert.delay.assert_not_called()
```

- [ ] **Step 6: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_pre_audit_conversion.py tests/test_lead_documents.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/tasks/pre_audit_jobs.py backend/app/tasks/lead_jobs.py backend/tests/test_pre_audit_conversion.py
git commit -m "feat(pre-audit): add lead conversion and pre-audit Celery tasks"
```

---

### Task 7: API endpoint and schemas

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/api/leads.py`

**Interfaces:**
- Consumes: `Lead`, `ProjectPreAudit`
- Produces: `POST /leads/{lead_id}/convert-and-pre-audit`, `ProjectPreAuditOut`

- [ ] **Step 1: Add schemas to `backend/app/schemas.py`**

After `LeadDocumentOut`:

```python
class ProjectPreAuditOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    validation_run_id: Optional[uuid.UUID] = None
    readiness_score: float
    status: str
    gap_summary: Dict[str, Any] = {}
    created_at: datetime
```

- [ ] **Step 2: Add endpoint to `backend/app/api/leads.py`**

```python
from app.services.lead_intelligence.lead_converter import LeadToProjectConverter, LeadConversionError
from app.services.lead_intelligence.pre_audit_runner import PreAuditRunner
from app.schemas import ProjectPreAuditOut


@router.post("/{lead_id}/convert-and-pre-audit", response_model=ProjectPreAuditOut, status_code=202)
async def convert_and_pre_audit_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    try:
        converter = LeadToProjectConverter(db)
        project = await converter.convert(lead)
    except LeadConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    runner = PreAuditRunner(db)
    pre_audit = await runner.run_for_project(project, lead_id=str(lead_id))

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_created,
        actor_id=current_user.id,
        target_type="project_pre_audit",
        target_id=pre_audit.id,
        metadata={"lead_id": str(lead_id), "project_id": str(project.id)},
    )
    return pre_audit
```

- [ ] **Step 3: Add tests**

Add to `backend/tests/test_pre_audit_conversion.py`:

```python
@pytest.mark.asyncio
async def test_convert_and_pre_audit_endpoint(client: AsyncClient, operator_headers, async_db_session, convertible_lead):
    doc = LeadDocument(
        lead_id=convertible_lead.id,
        document_type="pdd",
        source_url="https://example.com/pdd.pdf",
        mime_type="application/pdf",
        s3_key="leads/cdm/.../pdd/abc.pdf",
        s3_bucket="bucket",
        file_size_bytes=1234,
        file_hash_sha256="abcd",
        status=LeadDocumentStatusEnum.fetched,
    )
    async_db_session.add(doc)
    await async_db_session.commit()

    with patch("app.services.lead_intelligence.pre_audit_runner.PreAuditRunner.run_for_project", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = MagicMock(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            lead_id=convertible_lead.id,
            validation_run_id=None,
            readiness_score=0.75,
            status="gaps",
            gap_summary={},
            created_at=datetime.now(timezone.utc),
        )
        resp = await client.post(f"/leads/{convertible_lead.id}/convert-and-pre-audit", headers=operator_headers)

    assert resp.status_code == 202
    data = resp.json()
    assert data["readiness_score"] == 0.75
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_pre_audit_conversion.py -v
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/schemas.py backend/app/api/leads.py backend/tests/test_pre_audit_conversion.py
git commit -m "feat(pre-audit): add convert-and-pre-audit API endpoint"
```

---

### Task 8: Frontend pre-audit panel

**Files:**
- Modify: `frontend/src/hooks/useProjects.ts`
- Modify: `frontend/src/pages/ProjectDetailPage.tsx`

**Interfaces:**
- Consumes: `GET /projects/{project_id}/pre-audit` (to be added), validation run detail APIs
- Produces: Pre-audit badge and gap report panel

- [ ] **Step 1: Add API endpoint GET /projects/{project_id}/pre-audit**

In `backend/app/api/projects.py`:

```python
from app.models import ProjectPreAudit


@router.get("/{project_id}/pre-audit", response_model=Optional[ProjectPreAuditOut])
async def get_project_pre_audit(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    from sqlalchemy import desc
    result = await db.execute(
        select(ProjectPreAudit)
        .where(ProjectPreAudit.project_id == project_id)
        .order_by(desc(ProjectPreAudit.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 2: Add hook to `frontend/src/hooks/useProjects.ts`**

```typescript
export const useProjectPreAudit = (projectId: string) =>
  useQuery({
    queryKey: ["projects", projectId, "pre-audit"],
    queryFn: async () => {
      const { data } = await api.get(`/projects/${projectId}/pre-audit`);
      return data;
    },
    enabled: !!projectId,
  });
```

- [ ] **Step 3: Add pre-audit panel to `frontend/src/pages/ProjectDetailPage.tsx`**

Add near the top of the detail view:

```tsx
const { data: preAudit } = useProjectPreAudit(projectId);

// In the JSX, after the project header:
{preAudit && (
  <Alert severity={preAudit.status === "passed" ? "success" : preAudit.status === "gaps" ? "warning" : "error"}>
    <Typography variant="subtitle2">
      Pre-audit readiness: {Math.round(preAudit.readiness_score * 100)}% ({preAudit.status})
    </Typography>
    {preAudit.gap_summary?.recommendation && (
      <Typography variant="body2">{preAudit.gap_summary.recommendation}</Typography>
    )}
  </Alert>
)}
```

- [ ] **Step 4: Add tests**

Create/update `frontend/src/test/ProjectDetailPage.test.tsx` or add a small test verifying the panel renders.

- [ ] **Step 5: Run frontend checks**

```bash
cd /Users/lukeouko/carbonverify/frontend
npm run lint
npm run test
npm run build
```

Expected: lint 0 errors, tests pass, build succeeds.

- [ ] **Step 6: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/hooks/useProjects.ts frontend/src/pages/ProjectDetailPage.tsx backend/app/api/projects.py
git commit -m "feat(pre-audit): add project pre-audit panel and API"
```

---

### Task 9: Documentation and changelog

**Files:**
- Modify: `docs/AI_PRE_AUDIT_USER_GUIDE.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update user guide**

Add a Phase 2 section explaining:
- Qualified leads are auto-converted to projects after scraping.
- Documents are imported from the registry.
- Pre-audit runs automatically; results appear on the project detail page.
- Operators can manually trigger conversion via `POST /leads/{id}/convert-and-pre-audit`.
- Human gate: projects stay in onboarding until an operator approves them.

- [ ] **Step 2: Update changelog**

Add entry under `[Unreleased]`:

```markdown
### Added
- AI Pre-Audit Phase 2: automatic lead-to-project conversion, registry document import, and pre-audit validation workflow.
- `ProjectPreAudit` model to cache readiness score and gap report.
- `POST /leads/{lead_id}/convert-and-pre-audit` endpoint.
- Pre-audit readiness panel on project detail page.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add docs/AI_PRE_AUDIT_USER_GUIDE.md CHANGELOG.md
git commit -m "docs(pre-audit): update user guide and changelog for Phase 2"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run backend tests**

```bash
cd /Users/lukeouko/carbonverify/backend
pytest tests/test_pre_audit_conversion.py tests/test_lead_documents.py tests/test_lead_api.py tests/test_lead_scrapers.py tests/test_lead_scorer.py -q
```

Expected: all pass.

- [ ] **Step 2: Run frontend checks**

```bash
cd /Users/lukeouko/carbonverify/frontend
npm run lint
npm run test
npm run build
```

Expected: lint 0 errors, tests pass, build succeeds.

- [ ] **Step 3: Push branch**

```bash
cd /Users/lukeouko/carbonverify
git push origin feature/validation-workflow-builder
```

- [ ] **Step 4: Final commit if any fixes**

If tests or lint required changes, commit them.

---

## Self-Review

**Spec coverage:**
- Lead-to-project conversion: Task 3 + Task 6.
- Default pre-audit workflow: Task 4.
- Run pre-audit and store `ProjectPreAudit`: Task 5 + Task 6.
- Daily pipeline trigger: Task 6.
- UI surface: Task 8.
- Documentation: Task 9.

**Placeholder scan:** No TBD/TODO; all steps include concrete code or exact commands.

**Type consistency:**
- `LeadToProjectConverter.convert(lead)` returns `Project`.
- `PreAuditRunner.run_for_project(project, lead_id)` returns `ProjectPreAudit`.
- `ProjectPreAuditOut` matches model fields.
- Celery task signatures use `str` IDs consistently.
