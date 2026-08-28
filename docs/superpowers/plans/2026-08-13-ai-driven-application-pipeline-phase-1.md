# AI-Driven Application Pipeline — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core intake layer for the AI-driven carbon-credit application pipeline: database models, REST API, secure public upload tokens, three new validation workflow step executors, and a public intake portal.

**Architecture:** Extend the existing `validation_engine` with domain-specific step types (`application_intake`, `document_collection`, `document_ai_classification`) that operate on a new `Application` entity. The frontend gets a multi-step public intake wizard. All changes follow existing SQLAlchemy 2.0, Pydantic v2, FastAPI, and React patterns.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, PostgreSQL, React 18 + TypeScript + Vite, Tailwind CSS, React Query v5, Zustand.

## Global Constraints

- Use `Mapped[type] = mapped_column(...)` SQLAlchemy 2.0 style.
- Use Pydantic v2 (`model_validate`, `model_dump`) in all schemas.
- All DB operations must be `async`/`await`.
- All new API routes must use RBAC dependencies from `app.auth.dependencies`.
- Encrypt PII (email) at rest using `EncryptedString` and store a searchable hash.
- New validation workflow step types must be added to `WorkflowStepType` enum and registered in `StepExecutorRegistry`.
- Frontend must use React Query v5 hooks pattern and Tailwind utility classes.
- Each task ends with a passing test and a commit.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/app/models.py` | Add `Application`, `ApplicationDocument`, `ApplicationStatusEnum`, `ApplicationDocumentSourceEnum`, `ApplicationDocumentTypeEnum` |
| `backend/alembic/versions/XXXX_add_application_tables.py` | Migration for new tables and enums |
| `backend/app/schemas.py` | Add `ApplicationBase`, `ApplicationCreate`, `ApplicationUpdate`, `ApplicationOut`, `ApplicationDocumentOut`, `ApplicationIntakeRequest` |
| `backend/app/api/applications.py` | REST API for applications and public upload endpoints |
| `backend/app/services/application_tokens.py` | JWT-based secure applicant upload tokens |
| `backend/app/validation_engine/models.py` | Extend `WorkflowStepType` enum |
| `backend/app/validation_engine/executors.py` | Add `ApplicationIntakeExecutor`, `DocumentCollectionExecutor`, `DocumentAiClassificationExecutor` |
| `backend/app/validation_engine/executor_registry.py` (new) | Move registry out of `executors.py` to avoid circular imports |
| `backend/app/services/application_pipeline.py` | Helper to create the default `ai_application_pipeline` workflow template |
| `backend/app/main.py` | Include `applications_router` |
| `frontend/src/pages/ApplicationIntakePage.tsx` | Public multi-step intake wizard |
| `frontend/src/pages/ApplicationIntakeSuccessPage.tsx` | Success + applicant dashboard link |
| `frontend/src/hooks/useApplications.ts` | React Query hooks |
| `frontend/src/services/applicationsApi.ts` | Axios calls |
| `frontend/src/App.tsx` | Add public route |
| `backend/tests/test_applications.py` | API tests |
| `backend/tests/test_application_executors.py` | Executor tests |

---

## Task 1: Database Models and Migration

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/XXXX_add_application_tables.py`
- Test: `backend/tests/test_applications.py`

**Interfaces:**
- Produces: `Application`, `ApplicationDocument`, `ApplicationStatusEnum`, `ApplicationDocumentSourceEnum`, `ApplicationDocumentTypeEnum`, `ApplicationDocumentStatusEnum`.

- [ ] **Step 1: Write the failing migration test**

```python
# backend/tests/test_applications.py
import pytest
from sqlalchemy import select
from app.models import Application, ApplicationStatusEnum


@pytest.mark.asyncio
async def test_application_model_exists(client, db_session):
    app = Application(
        applicant_email_hash="test@example.com",
        project_title="Test Stove Project",
        country="Kenya",
        sector="cookstoves",
        status=ApplicationStatusEnum.intake,
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    result = await db_session.execute(select(Application).where(Application.id == app.id))
    fetched = result.scalar_one()
    assert fetched.project_title == "Test Stove Project"
    assert fetched.status == ApplicationStatusEnum.intake
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
source .venv/bin/activate
pytest tests/test_applications.py::test_application_model_exists -v
```

Expected: FAIL with `ImportError: cannot import name 'Application'`.

- [ ] **Step 3: Add enums and models to `backend/app/models.py`**

Insert near other enums (around line 150):

```python
class ApplicationStatusEnum(str, PyEnum):
    intake = "intake"
    documents_pending = "documents_pending"
    pre_audit = "pre_audit"
    gaps = "gaps"
    ready_for_calculation = "ready_for_calculation"
    ready_for_review = "ready_for_review"
    approved = "approved"
    submitted = "submitted"
    rejected = "rejected"


class ApplicationDocumentSourceEnum(str, PyEnum):
    upload = "upload"
    email = "email"
    drive = "drive"
    dropbox = "dropbox"
    registry = "registry"
    api = "api"


class ApplicationDocumentTypeEnum(str, PyEnum):
    pdd = "pdd"
    monitoring_report = "monitoring_report"
    kpt_results = "kpt_results"
    sales_receipt = "sales_receipt"
    survey_form = "survey_form"
    gps_data = "gps_data"
    stove_inventory = "stove_inventory"
    other = "other"


class ApplicationDocumentStatusEnum(str, PyEnum):
    discovered = "discovered"
    fetched = "fetched"
    scanning = "scanning"
    processed = "processed"
    failed = "failed"
```

Insert models near the Lead section (after `PortfolioHolding`):

```python
class Application(Base):
    __tablename__ = "applications"

    __table_args__ = (
        Index("ix_applications_status", "status"),
        Index("ix_applications_country", "country"),
        Index("ix_applications_sector", "sector"),
        Index("ix_applications_applicant_email_hash", "applicant_email_hash"),
        Index("ix_applications_converted_project_id", "converted_project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    applicant_email_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    applicant_email_encrypted: Mapped[Optional[str]] = mapped_column(EncryptedString(255), nullable=True)
    organization_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    project_title: Mapped[str] = mapped_column(String(500), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proposed_methodology: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[ApplicationStatusEnum] = mapped_column(
        Enum(ApplicationStatusEnum, name="application_status"), nullable=False, default=ApplicationStatusEnum.intake
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    converted_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    validation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    documents: Mapped[List["ApplicationDocument"]] = relationship(
        "ApplicationDocument", back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    __table_args__ = (
        Index("ix_application_documents_application_id", "application_id"),
        Index("ix_application_documents_status", "status"),
        Index("ix_application_documents_document_type", "document_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False
    )
    source_type: Mapped[ApplicationDocumentSourceEnum] = mapped_column(
        Enum(ApplicationDocumentSourceEnum, name="application_document_source"), nullable=False
    )
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    s3_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    file_hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    document_type: Mapped[Optional[ApplicationDocumentTypeEnum]] = mapped_column(
        Enum(ApplicationDocumentTypeEnum, name="application_document_type"), nullable=True
    )
    status: Mapped[ApplicationDocumentStatusEnum] = mapped_column(
        Enum(ApplicationDocumentStatusEnum, name="application_document_status"),
        nullable=False,
        default=ApplicationDocumentStatusEnum.discovered,
    )
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_entities: Mapped[dict] = mapped_column(JSONB, default=dict)
    gap_findings: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    application: Mapped["Application"] = relationship("Application", back_populates="documents")
```

- [ ] **Step 4: Generate the migration**

```bash
cd backend
alembic revision --autogenerate -m "add application tables"
```

- [ ] **Step 5: Run the migration locally**

```bash
cd backend
alembic upgrade head
```

- [ ] **Step 6: Run the test**

```bash
cd backend
pytest tests/test_applications.py::test_application_model_exists -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/alembic/versions/XXXX_add_application_tables.py backend/tests/test_applications.py
git commit -m "feat(applications): add Application and ApplicationDocument models"
```

---

## Task 2: Pydantic Schemas

**Files:**
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_applications.py`

**Interfaces:**
- Consumes: `ApplicationStatusEnum`, `ApplicationDocumentSourceEnum`, `ApplicationDocumentTypeEnum`, `ApplicationDocumentStatusEnum`.
- Produces: `ApplicationBase`, `ApplicationCreate`, `ApplicationUpdate`, `ApplicationOut`, `ApplicationDocumentOut`, `ApplicationIntakeRequest`.

- [ ] **Step 1: Write the failing schema test**

```python
# backend/tests/test_applications.py
from app.schemas import ApplicationCreate, ApplicationOut


def test_application_schema_roundtrip():
    data = {
        "applicant_email_hash": "test@example.com",
        "project_title": "Test",
        "country": "Kenya",
        "sector": "cookstoves",
        "status": "intake",
    }
    created = ApplicationCreate.model_validate(data)
    assert created.project_title == "Test"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_applications.py::test_application_schema_roundtrip -v
```

Expected: FAIL with `ImportError: cannot import name 'ApplicationCreate'`.

- [ ] **Step 3: Add schemas**

Insert near the Lead schemas in `backend/app/schemas.py`:

```python
# ─── AI Application Pipeline ────────────────────────────────────────────────────

class ApplicationBase(BaseModel):
    applicant_email_hash: str
    applicant_email_encrypted: Optional[str] = None
    organization_name: Optional[str] = None
    project_title: str
    country: Optional[str] = None
    region: Optional[str] = None
    sector: Optional[str] = None
    proposed_methodology: Optional[str] = None
    status: str = "intake"
    confidence_score: float = 0.0


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    organization_name: Optional[str] = None
    project_title: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    sector: Optional[str] = None
    proposed_methodology: Optional[str] = None
    status: Optional[str] = None
    confidence_score: Optional[float] = None
    converted_project_id: Optional[uuid.UUID] = None
    validation_run_id: Optional[uuid.UUID] = None


class ApplicationOut(ApplicationBase, ORMBase):
    id: uuid.UUID
    converted_project_id: Optional[uuid.UUID] = None
    validation_run_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ApplicationDocumentOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    source_type: str
    source_url: Optional[str] = None
    s3_key: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    file_hash_sha256: Optional[str] = None
    document_type: Optional[str] = None
    status: str
    extracted_text: Optional[str] = None
    extracted_entities: dict = Field(default_factory=dict)
    gap_findings: dict = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationIntakeRequest(BaseModel):
    applicant_email: EmailStr
    organization_name: Optional[str] = None
    project_title: str
    country: Optional[str] = None
    sector: Optional[str] = None
    proposed_methodology: Optional[str] = None
```

- [ ] **Step 4: Run the test**

```bash
cd backend
pytest tests/test_applications.py::test_application_schema_roundtrip -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_applications.py
git commit -m "feat(applications): add Pydantic schemas"
```

---

## Task 3: Secure Applicant Upload Tokens

**Files:**
- Create: `backend/app/services/application_tokens.py`
- Test: `backend/tests/test_application_tokens.py`

**Interfaces:**
- Produces: `create_applicant_token(application_id)`, `verify_applicant_token(token) -> uuid.UUID`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_application_tokens.py
import uuid
import pytest
from app.services.application_tokens import create_applicant_token, verify_applicant_token


@pytest.mark.asyncio
async def test_applicant_token_roundtrip():
    app_id = uuid.uuid4()
    token = create_applicant_token(app_id)
    assert isinstance(token, str)
    verified = verify_applicant_token(token)
    assert verified == app_id
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_application_tokens.py::test_applicant_token_roundtrip -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.application_tokens'`.

- [ ] **Step 3: Implement token service**

```python
# backend/app/services/application_tokens.py
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def create_applicant_token(application_id: uuid.UUID, expires_days: int = TOKEN_EXPIRE_DAYS) -> str:
    """Create a time-limited JWT for public applicant access."""
    expire = datetime.now(timezone.utc) + timedelta(days=expires_days)
    payload = {
        "sub": str(application_id),
        "type": "applicant",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_applicant_token(token: str) -> Optional[uuid.UUID]:
    """Verify an applicant token and return the application_id, or None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "applicant":
            return None
        app_id = uuid.UUID(payload.get("sub"))
        return app_id
    except (JWTError, ValueError, TypeError):
        return None
```

- [ ] **Step 4: Run the test**

```bash
cd backend
pytest tests/test_application_tokens.py::test_applicant_token_roundtrip -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/application_tokens.py backend/tests/test_application_tokens.py
git commit -m "feat(applications): add secure applicant JWT tokens"
```

---

## Task 4: Applications API

**Files:**
- Create: `backend/app/api/applications.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_applications.py`

**Interfaces:**
- Consumes: `Application` models, schemas, token service.
- Produces: `/applications` endpoints.

- [ ] **Step 1: Write the failing API test**

```python
# backend/tests/test_applications.py
import uuid
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_application(client: AsyncClient, db_session):
    payload = {
        "applicant_email": "dev@example.com",
        "project_title": "Kenya Cookstoves",
        "country": "Kenya",
        "sector": "cookstoves",
    }
    response = await client.post("/applications", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["project_title"] == "Kenya Cookstoves"
    assert data["status"] == "intake"
    assert "applicant_token" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_applications.py::test_create_application -v
```

Expected: FAIL with 404 or `Connection refused` because router is not included.

- [ ] **Step 3: Implement the API router**

```python
# backend/app/api/applications.py
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import (
    Application,
    ApplicationDocument,
    ApplicationStatusEnum,
    ApplicationDocumentStatusEnum,
    User,
)
from app.schemas import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationOut,
    ApplicationDocumentOut,
    ApplicationIntakeRequest,
)
from app.auth.dependencies import require_viewer, require_operator, require_admin
from app.services.application_tokens import create_applicant_token, verify_applicant_token
from app.services.encryption import compute_searchable_hash
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationIntakeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint for project owners to submit an intake application."""
    email_hash = compute_searchable_hash(payload.applicant_email)
    application = Application(
        applicant_email_hash=email_hash,
        applicant_email_encrypted=payload.applicant_email,
        organization_name=payload.organization_name,
        project_title=payload.project_title,
        country=payload.country,
        sector=payload.sector,
        proposed_methodology=payload.proposed_methodology,
        status=ApplicationStatusEnum.intake,
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)

    token = create_applicant_token(application.id)
    response_data = ApplicationOut.model_validate(application).model_dump()
    response_data["applicant_token"] = token
    return response_data


@router.get("", response_model=List[ApplicationOut])
async def list_applications(
    status: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Application)
    if status:
        stmt = stmt.where(Application.status == status)
    if country:
        stmt = stmt.where(Application.country.ilike(f"%{country}%"))
    if sector:
        stmt = stmt.where(Application.sector == sector)
    stmt = stmt.order_by(Application.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(Application).where(Application.id == application_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.patch("/{application_id}", response_model=ApplicationOut)
async def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(Application).where(Application.id == application_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(app, key, value)

    await db.commit()
    await db.refresh(app)
    return app


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Application).where(Application.id == application_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await db.delete(app)
    await db.commit()


@router.get("/{application_id}/documents", response_model=List[ApplicationDocumentOut])
async def list_application_documents(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(ApplicationDocument).where(ApplicationDocument.application_id == application_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{application_id}/trigger-pipeline", response_model=ApplicationOut)
async def trigger_application_pipeline(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Trigger the ai_application_pipeline validation workflow for an application."""
    result = await db.execute(select(Application).where(Application.id == application_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Placeholder for Phase 2: actually create/run ValidationRun
    logger.info("pipeline_triggered", application_id=str(application_id))
    return app
```

- [ ] **Step 4: Include the router in `backend/app/main.py`**

Add import near other router imports:

```python
from app.api.applications import router as applications_router
```

Add include near other routers:

```python
app.include_router(applications_router)
```

- [ ] **Step 5: Run the test**

```bash
cd backend
pytest tests/test_applications.py::test_create_application -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/applications.py backend/app/main.py backend/tests/test_applications.py
git commit -m "feat(applications): add applications REST API"
```

---

## Task 5: Extend Workflow Step Types

**Files:**
- Modify: `backend/app/validation_engine/models.py`
- Modify: `backend/app/validation_engine/schemas.py`
- Test: `backend/tests/test_application_executors.py`

**Interfaces:**
- Produces: new `WorkflowStepType` enum values and config schemas.

- [ ] **Step 1: Write the failing enum test**

```python
# backend/tests/test_application_executors.py
from app.validation_engine.models import WorkflowStepType


def test_application_step_types_exist():
    assert WorkflowStepType.application_intake.value == "application_intake"
    assert WorkflowStepType.document_collection.value == "document_collection"
    assert WorkflowStepType.document_ai_classification.value == "document_ai_classification"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_application_executors.py::test_application_step_types_exist -v
```

Expected: FAIL with `AttributeError: application_intake`.

- [ ] **Step 3: Add enum values**

In `backend/app/validation_engine/models.py`, extend `WorkflowStepType`:

```python
class WorkflowStepType(str, PyEnum):
    http_request = "http_request"
    database_query = "database_query"
    service_call = "service_call"
    external_api = "external_api"
    notification = "notification"
    dom_capture = "dom_capture"
    decision_gate = "decision_gate"
    ai_evaluation = "ai_evaluation"
    wait = "wait"
    parallel = "parallel"
    subflow = "subflow"
    application_intake = "application_intake"
    document_collection = "document_collection"
    document_ai_classification = "document_ai_classification"
```

- [ ] **Step 4: Add config schemas**

In `backend/app/validation_engine/schemas.py`, add near other config schemas:

```python
class ApplicationIntakeConfig(BaseModel):
    applicant_email: str
    project_title: str
    organization_name: Optional[str] = None
    country: Optional[str] = None
    sector: Optional[str] = None
    proposed_methodology: Optional[str] = None


class DocumentCollectionConfig(BaseModel):
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    required_document_types: List[str] = Field(default_factory=list)


class DocumentAiClassificationConfig(BaseModel):
    classify_with_kimi: bool = True
    extract_entities: bool = True
```

- [ ] **Step 5: Run the test**

```bash
cd backend
pytest tests/test_application_executors.py::test_application_step_types_exist -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/validation_engine/models.py backend/app/validation_engine/schemas.py backend/tests/test_application_executors.py
git commit -m "feat(validation_engine): add application pipeline step types"
```

---

## Task 6: Application Intake Executor

**Files:**
- Modify: `backend/app/validation_engine/executors.py`
- Test: `backend/tests/test_application_executors.py`

**Interfaces:**
- Consumes: `ApplicationIntakeConfig`, `Application` model, `compute_searchable_hash`.
- Produces: `ApplicationIntakeExecutor` returning `application_id`, `status`, `confidence_score`.

- [ ] **Step 1: Write the failing executor test**

```python
# backend/tests/test_application_executors.py
import pytest
from app.validation_engine.executors import ApplicationIntakeExecutor
from app.validation_engine.schemas import ApplicationIntakeConfig
from app.validation_engine.models import ValidationRun


@pytest.mark.asyncio
async def test_application_intake_executor(db_session):
    executor = ApplicationIntakeExecutor()
    config = ApplicationIntakeConfig(
        applicant_email="owner@example.com",
        project_title="Test Project",
        country="Kenya",
        sector="cookstoves",
    ).model_dump()
    run = ValidationRun(id=uuid.uuid4())

    result = await executor.execute(config, {}, run)

    assert result["project_title"] == "Test Project"
    assert result["status"] == "intake"
    assert "application_id" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_application_executors.py::test_application_intake_executor -v
```

Expected: FAIL with `ImportError: ApplicationIntakeExecutor`.

- [ ] **Step 3: Implement the executor**

Add to `backend/app/validation_engine/executors.py`:

```python
class ApplicationIntakeExecutor:
    """Create an Application record from workflow config."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.database import get_db_context
        from app.models import Application, ApplicationStatusEnum
        from app.services.encryption import compute_searchable_hash

        cfg = ApplicationIntakeConfig.model_validate(config)
        email_hash = compute_searchable_hash(cfg.applicant_email)

        application = Application(
            applicant_email_hash=email_hash,
            applicant_email_encrypted=cfg.applicant_email,
            organization_name=cfg.organization_name,
            project_title=cfg.project_title,
            country=cfg.country,
            sector=cfg.sector,
            proposed_methodology=cfg.proposed_methodology,
            status=ApplicationStatusEnum.intake,
            confidence_score=0.95,
        )

        async with get_db_context() as db:
            db.add(application)
            await db.commit()
            await db.refresh(application)

        return {
            "application_id": str(application.id),
            "project_title": application.project_title,
            "status": application.status.value,
            "confidence_score": application.confidence_score,
        }
```

Note: `get_db_context` may not exist. If it does not, add it to `backend/app/database.py`:

```python
@asynccontextmanager
async def get_db_context() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

- [ ] **Step 4: Run the test**

```bash
cd backend
pytest tests/test_application_executors.py::test_application_intake_executor -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/validation_engine/executors.py backend/app/database.py backend/tests/test_application_executors.py
git commit -m "feat(validation_engine): add ApplicationIntakeExecutor"
```

---

## Task 7: Document Collection Executor

**Files:**
- Modify: `backend/app/validation_engine/executors.py`
- Test: `backend/tests/test_application_executors.py`

**Interfaces:**
- Consumes: `DocumentCollectionConfig`, `ApplicationDocument` model.
- Produces: `DocumentCollectionExecutor` returning collected document metadata.

- [ ] **Step 1: Write the failing executor test**

```python
@pytest.mark.asyncio
async def test_document_collection_executor(db_session, sample_application):
    executor = DocumentCollectionExecutor()
    config = DocumentCollectionConfig(
        sources=[{"type": "upload", "folder_id": None}],
        required_document_types=["pdd"],
    ).model_dump()
    run = ValidationRun(id=uuid.uuid4())
    context = {"application_id": str(sample_application.id)}

    result = await executor.execute(config, context, run)

    assert "collected_documents" in result
    assert result["status"] == "awaiting_documents"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_application_executors.py::test_document_collection_executor -v
```

Expected: FAIL with `ImportError: DocumentCollectionExecutor`.

- [ ] **Step 3: Implement the executor**

Add to `backend/app/validation_engine/executors.py`:

```python
class DocumentCollectionExecutor:
    """Record discovered document slots for an application and await uploads."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from sqlalchemy import select
        from app.database import get_db_context
        from app.models import (
            Application,
            ApplicationDocument,
            ApplicationDocumentSourceEnum,
            ApplicationDocumentStatusEnum,
            ApplicationStatusEnum,
        )

        cfg = DocumentCollectionConfig.model_validate(config)
        application_id = uuid.UUID(context.get("application_id"))

        async with get_db_context() as db:
            result = await db.execute(select(Application).where(Application.id == application_id))
            application = result.scalar_one_or_none()
            if not application:
                raise RuntimeError(f"Application {application_id} not found")

            collected = []
            for source in cfg.sources:
                doc = ApplicationDocument(
                    application_id=application_id,
                    source_type=ApplicationDocumentSourceEnum(source.get("type", "upload")),
                    source_url=source.get("url"),
                    status=ApplicationDocumentStatusEnum.discovered,
                )
                db.add(doc)
                collected.append({"document_id": str(doc.id), "status": "discovered"})

            application.status = ApplicationStatusEnum.documents_pending
            await db.commit()

        return {
            "application_id": str(application_id),
            "collected_documents": collected,
            "required_document_types": cfg.required_document_types,
            "status": "awaiting_documents",
            "confidence_score": 0.7,
        }
```

- [ ] **Step 4: Run the test**

```bash
cd backend
pytest tests/test_application_executors.py::test_document_collection_executor -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/validation_engine/executors.py backend/tests/test_application_executors.py
git commit -m "feat(validation_engine): add DocumentCollectionExecutor"
```

---

## Task 8: Document AI Classification Executor

**Files:**
- Modify: `backend/app/validation_engine/executors.py`
- Test: `backend/tests/test_application_executors.py`

**Interfaces:**
- Consumes: `DocumentAiClassificationConfig`, `ApplicationDocument` records.
- Produces: `DocumentAiClassificationExecutor` returning classified documents and extracted entities.

- [ ] **Step 1: Write the failing executor test**

```python
@pytest.mark.asyncio
async def test_document_ai_classification_executor(db_session, sample_document):
    executor = DocumentAiClassificationExecutor()
    config = DocumentAiClassificationConfig(classify_with_kimi=False).model_dump()
    run = ValidationRun(id=uuid.uuid4())
    context = {"application_id": str(sample_document.application_id)}

    result = await executor.execute(config, context, run)

    assert "classified_documents" in result
    assert result["classified_documents"][0]["document_type"] == "other"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_application_executors.py::test_document_ai_classification_executor -v
```

Expected: FAIL with `ImportError: DocumentAiClassificationExecutor`.

- [ ] **Step 3: Implement the executor**

Add to `backend/app/validation_engine/executors.py`:

```python
class DocumentAiClassificationExecutor:
    """Classify application documents and extract entities."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from sqlalchemy import select
        from app.database import get_db_context
        from app.models import (
            ApplicationDocument,
            ApplicationDocumentStatusEnum,
            ApplicationDocumentTypeEnum,
        )
        from app.services.kimi_api import KimiAPIClient

        cfg = DocumentAiClassificationConfig.model_validate(config)
        application_id = uuid.UUID(context.get("application_id"))

        async with get_db_context() as db:
            result = await db.execute(
                select(ApplicationDocument).where(ApplicationDocument.application_id == application_id)
            )
            documents = result.scalars().all()

            classified = []
            for doc in documents:
                if cfg.classify_with_kimi and doc.extracted_text:
                    kimi = KimiAPIClient()
                    prompt = (
                        "Classify this carbon-credit project document into one of: "
                        "pdd, monitoring_report, kpt_results, sales_receipt, survey_form, "
                        "gps_data, stove_inventory, other. "
                        "Return only the document type.\n\n"
                        f"Text excerpt:\n{doc.extracted_text[:2000]}"
                    )
                    response = await kimi.chat_completion(messages=[{"role": "user", "content": prompt}])
                    doc_type = (response.get("content", "") or "other").strip().lower()
                    if doc_type not in [e.value for e in ApplicationDocumentTypeEnum]:
                        doc_type = "other"
                else:
                    doc_type = "other"

                doc.document_type = ApplicationDocumentTypeEnum(doc_type)
                doc.status = ApplicationDocumentStatusEnum.processed
                classified.append({
                    "document_id": str(doc.id),
                    "document_type": doc_type,
                    "status": doc.status.value,
                })

            await db.commit()

        return {
            "application_id": str(application_id),
            "classified_documents": classified,
            "confidence_score": 0.85 if cfg.classify_with_kimi else 0.6,
        }
```

- [ ] **Step 4: Run the test**

```bash
cd backend
pytest tests/test_application_executors.py::test_document_ai_classification_executor -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/validation_engine/executors.py backend/tests/test_application_executors.py
git commit -m "feat(validation_engine): add DocumentAiClassificationExecutor"
```

---

## Task 9: Register New Executors

**Files:**
- Modify: `backend/app/validation_engine/executors.py` (registry)
- Test: `backend/tests/test_application_executors.py`

- [ ] **Step 1: Write the failing registry test**

```python
def test_application_executors_registered():
    from app.validation_engine.executors import StepExecutorRegistry
    from app.validation_engine.models import WorkflowStepType

    registry = StepExecutorRegistry()
    assert registry.get_executor(WorkflowStepType.application_intake) is not None
    assert registry.get_executor(WorkflowStepType.document_collection) is not None
    assert registry.get_executor(WorkflowStepType.document_ai_classification) is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_application_executors.py::test_application_executors_registered -v
```

Expected: FAIL with `ValueError: No executor registered`.

- [ ] **Step 3: Register executors**

In `backend/app/validation_engine/executors.py`, update `StepExecutorRegistry.__init__`:

```python
self._executors: Dict[WorkflowStepType, StepExecutor] = {
    # ... existing executors ...
    WorkflowStepType.application_intake: ApplicationIntakeExecutor(),
    WorkflowStepType.document_collection: DocumentCollectionExecutor(),
    WorkflowStepType.document_ai_classification: DocumentAiClassificationExecutor(),
}
```

- [ ] **Step 4: Run the test**

```bash
cd backend
pytest tests/test_application_executors.py::test_application_executors_registered -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/validation_engine/executors.py backend/tests/test_application_executors.py
git commit -m "feat(validation_engine): register application pipeline executors"
```

---

## Task 10: Default AI Application Pipeline Workflow Template

**Files:**
- Create: `backend/app/services/application_pipeline.py`
- Modify: `backend/app/tasks/application_jobs.py` (new)
- Test: `backend/tests/test_application_pipeline.py`

**Interfaces:**
- Produces: `ensure_default_application_pipeline()` idempotently creates the workflow template.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_application_pipeline.py
import pytest
from app.services.application_pipeline import ensure_default_application_pipeline
from app.validation_engine.models import ValidationWorkflow


@pytest.mark.asyncio
async def test_default_pipeline_exists(db_session):
    workflow = await ensure_default_application_pipeline(db_session)
    assert workflow.name == "ai_application_pipeline"
    assert "application_intake" in workflow.workflow_graph["steps"][0]["step_type"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_application_pipeline.py::test_default_pipeline_exists -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the service**

```python
# backend/app/services/application_pipeline.py
import uuid
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.validation_engine.models import ValidationWorkflow
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_PIPELINE_NAME = "ai_application_pipeline"


def build_ai_application_pipeline_graph() -> Dict[str, Any]:
    return {
        "steps": [
            {
                "id": "intake",
                "step_type": "application_intake",
                "config": {
                    "applicant_email": "${input.applicant_email}",
                    "project_title": "${input.project_title}",
                    "organization_name": "${input.organization_name}",
                    "country": "${input.country}",
                    "sector": "${input.sector}",
                    "proposed_methodology": "${input.proposed_methodology}",
                },
                "next_on_success": "collect_documents",
            },
            {
                "id": "collect_documents",
                "step_type": "document_collection",
                "config": {
                    "sources": [{"type": "upload"}],
                    "required_document_types": ["pdd"],
                },
                "next_on_success": "classify_documents",
            },
            {
                "id": "classify_documents",
                "step_type": "document_ai_classification",
                "config": {"classify_with_kimi": True, "extract_entities": True},
                "next_on_success": None,
            },
        ],
        "entry_step": "intake",
    }


async def ensure_default_application_pipeline(db: AsyncSession) -> ValidationWorkflow:
    """Idempotently create the default AI application pipeline workflow template."""
    result = await db.execute(
        select(ValidationWorkflow).where(ValidationWorkflow.name == DEFAULT_PIPELINE_NAME)
    )
    workflow = result.scalar_one_or_none()
    if workflow:
        return workflow

    graph = build_ai_application_pipeline_graph()
    workflow = ValidationWorkflow(
        id=uuid.uuid4(),
        name=DEFAULT_PIPELINE_NAME,
        description="AI-driven carbon credit application intake, document collection, and classification pipeline.",
        workflow_graph=graph,
        is_active=True,
        version=1,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    logger.info("default_application_pipeline_created", workflow_id=str(workflow.id))
    return workflow
```

- [ ] **Step 4: Run the test**

```bash
cd backend
pytest tests/test_application_pipeline.py::test_default_pipeline_exists -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/application_pipeline.py backend/tests/test_application_pipeline.py
git commit -m "feat(applications): add default ai_application_pipeline workflow template"
```

---

## Task 11: Public Intake Portal Frontend

**Files:**
- Create: `frontend/src/pages/ApplicationIntakePage.tsx`
- Create: `frontend/src/pages/ApplicationIntakeSuccessPage.tsx`
- Create: `frontend/src/services/applicationsApi.ts`
- Create: `frontend/src/hooks/useApplications.ts`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/pages/__tests__/ApplicationIntakePage.test.tsx` (optional)

**Interfaces:**
- Consumes: `/applications` POST endpoint.
- Produces: Multi-step React form with validation.

- [ ] **Step 1: Add API service**

```typescript
// frontend/src/services/applicationsApi.ts
import axios from "axios";

export interface IntakePayload {
  applicant_email: string;
  organization_name?: string;
  project_title: string;
  country?: string;
  sector?: string;
  proposed_methodology?: string;
}

export interface IntakeResponse {
  id: string;
  applicant_token: string;
  project_title: string;
  status: string;
}

export const submitApplication = async (payload: IntakePayload): Promise<IntakeResponse> => {
  const { data } = await axios.post("/applications", payload);
  return data;
};
```

- [ ] **Step 2: Add React Query hook**

```typescript
// frontend/src/hooks/useApplications.ts
import { useMutation } from "@tanstack/react-query";
import { submitApplication, IntakePayload, IntakeResponse } from "../services/applicationsApi";

export const useSubmitApplication = () => {
  return useMutation<IntakeResponse, Error, IntakePayload>({
    mutationFn: submitApplication,
  });
};
```

- [ ] **Step 3: Build the intake page**

```tsx
// frontend/src/pages/ApplicationIntakePage.tsx
import { useState } from "react";
import { useSubmitApplication } from "../hooks/useApplications";

const SECTORS = ["cookstoves", "forestry", "renewable_energy", "agriculture", "waste"];
const METHODOLOGIES = ["VM0050", "VMR0006", "AMS-II.G", "TPDDTEC_v4", "Not sure"];

export default function ApplicationIntakePage() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    applicant_email: "",
    organization_name: "",
    project_title: "",
    country: "",
    sector: "",
    proposed_methodology: "",
  });
  const submit = useSubmitApplication();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    submit.mutate(form, {
      onSuccess: () => setStep(4),
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4">
      <div className="max-w-2xl mx-auto card p-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Apply for Carbon Credit Verification
        </h1>
        <p className="text-gray-600 dark:text-gray-300 mb-6">
          Our AI will review your documents and guide you through the audit-ready process.
        </p>

        {step === 4 ? (
          <div className="text-center py-8">
            <h2 className="text-xl font-semibold text-green-600 mb-2">Application received!</h2>
            <p className="text-gray-600 dark:text-gray-300">
              Check your email for a secure link to upload documents and track progress.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            {step === 1 && (
              <div className="space-y-4">
                <label className="block">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Email *</span>
                  <input
                    type="email"
                    name="applicant_email"
                    required
                    value={form.applicant_email}
                    onChange={handleChange}
                    className="input-modern w-full mt-1"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Organization</span>
                  <input
                    type="text"
                    name="organization_name"
                    value={form.organization_name}
                    onChange={handleChange}
                    className="input-modern w-full mt-1"
                  />
                </label>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-4">
                <label className="block">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Project Title *</span>
                  <input
                    type="text"
                    name="project_title"
                    required
                    value={form.project_title}
                    onChange={handleChange}
                    className="input-modern w-full mt-1"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Country</span>
                  <input
                    type="text"
                    name="country"
                    value={form.country}
                    onChange={handleChange}
                    className="input-modern w-full mt-1"
                  />
                </label>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4">
                <label className="block">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Sector</span>
                  <select name="sector" value={form.sector} onChange={handleChange} className="select-modern w-full mt-1">
                    <option value="">Select sector</option>
                    {SECTORS.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Proposed Methodology</span>
                  <select
                    name="proposed_methodology"
                    value={form.proposed_methodology}
                    onChange={handleChange}
                    className="select-modern w-full mt-1"
                  >
                    <option value="">Select methodology</option>
                    {METHODOLOGIES.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </label>
              </div>
            )}

            <div className="flex justify-between pt-4">
              {step > 1 && (
                <button type="button" onClick={() => setStep(step - 1)} className="btn-secondary">
                  Back
                </button>
              )}
              {step < 3 ? (
                <button type="button" onClick={() => setStep(step + 1)} className="btn-primary ml-auto">
                  Next
                </button>
              ) : (
                <button type="submit" disabled={submit.isPending} className="btn-primary ml-auto">
                  {submit.isPending ? "Submitting..." : "Submit Application"}
                </button>
              )}
            </div>

            {submit.isError && (
              <p className="text-red-600 text-sm">
                {submit.error?.message || "Submission failed. Please try again."}
              </p>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add route in `frontend/src/App.tsx`**

Add public route:

```tsx
<Route path="/apply" element={<ApplicationIntakePage />} />
```

- [ ] **Step 5: Build and run lint**

```bash
cd frontend
npm run build
npm run lint
```

Expected: Build succeeds with no new lint errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ApplicationIntakePage.tsx frontend/src/services/applicationsApi.ts frontend/src/hooks/useApplications.ts frontend/src/App.tsx
git commit -m "feat(frontend): add public application intake portal"
```

---

## Task 12: Full Phase 1 Integration Test

**Files:**
- Test: `backend/tests/test_application_pipeline.py`

- [ ] **Step 1: Write the integration test**

```python
@pytest.mark.asyncio
async def test_full_intake_to_classification_flow(client, db_session):
    # 1. Submit intake
    intake_response = await client.post("/applications", json={
        "applicant_email": "owner@example.com",
        "project_title": "Kenya Stoves",
        "country": "Kenya",
        "sector": "cookstoves",
    })
    assert intake_response.status_code == 201
    app_id = intake_response.json()["id"]

    # 2. Ensure pipeline template exists
    from app.services.application_pipeline import ensure_default_application_pipeline
    workflow = await ensure_default_application_pipeline(db_session)
    assert workflow.name == "ai_application_pipeline"

    # 3. Trigger pipeline (Phase 2 will actually run it end-to-end)
    trigger_response = await client.post(f"/applications/{app_id}/trigger-pipeline")
    assert trigger_response.status_code == 200
    assert trigger_response.json()["status"] == "intake"
```

- [ ] **Step 2: Run the test**

```bash
cd backend
pytest tests/test_application_pipeline.py::test_full_intake_to_classification_flow -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_application_pipeline.py
git commit -m "test(applications): add Phase 1 integration test"
```

---

## Task 13: Documentation Update

**Files:**
- Modify: `docs/AI_METHODOLOGY_DESIGNER.md` or create `docs/AI_APPLICATION_PIPELINE.md`

- [ ] **Step 1: Create user-facing doc**

```markdown
# AI Application Pipeline

## Overview
Project owners can apply for carbon credit verification directly on CarbonVerify. The AI intake pipeline collects project basics, guides document upload, classifies documents, and prepares the application for pre-audit.

## Public Intake
Visit `/apply` and complete the wizard. You will receive a secure email link to upload documents.

## Consultant View
Operators and admins can view applications at `/applications` (API) and in the Command Center (future).

## Automation Levels
- High-confidence classifications auto-advance.
- Medium-confidence items enter the human review queue.
- Low-confidence or missing documents trigger applicant requests.
```

- [ ] **Step 2: Commit**

```bash
git add docs/AI_APPLICATION_PIPELINE.md
git commit -m "docs: add AI application pipeline user guide"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** Phase 1 of the design spec (intake, document collection, classification) is covered.
- [ ] **Placeholder scan:** No TBD/TODO in code blocks.
- [ ] **Type consistency:** `ApplicationStatusEnum`, `ApplicationDocumentStatusEnum`, etc. are used consistently.
- [ ] **Tests:** Every task has a failing → passing test cycle.
- [ ] **RBAC:** Public intake endpoint is unauthenticated; list/get require viewer; update requires operator; delete requires admin.
- [ ] **PII:** Applicant email is encrypted with searchable hash.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-13-ai-driven-application-pipeline-phase-1.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach do you want?
