from datetime import date, datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
import json
import hashlib
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models import (
    Lead,
    LeadDocument,
    LeadDocumentStatusEnum,
    LeadProjectStatusEnum,
    LeadRegistrySourceEnum,
    LeadWorkflowStatusEnum,
    MethodologyEnum,
    PreAuditStatusEnum,
    Project,
    ProjectPreAudit,
    ProjectStatusEnum,
    User,
)
from app.services.lead_intelligence.document_text import extract_text_async
from app.services.lead_intelligence.lead_converter import LeadToProjectConverter, LeadConversionError
from app.services.lead_intelligence.pre_audit_runner import PreAuditRunner
from app.tasks.pre_audit_jobs import run_pre_audit_pipeline
from app.services.lead_intelligence.system_developer import (
    SYSTEM_COMPANY_NAME,
    SYSTEM_DEVELOPER_EMAIL,
    get_or_create_system_developer,
)
from app.validation_engine.orchestrator import ValidationOrchestrator


@pytest.mark.asyncio
async def test_get_or_create_system_developer(async_db_session):
    dev = await get_or_create_system_developer(async_db_session)
    assert dev.company_name == SYSTEM_COMPANY_NAME

    user_result = await async_db_session.execute(select(User).where(User.id == dev.user_id))
    user = user_result.scalar_one()
    assert user.email == SYSTEM_DEVELOPER_EMAIL
    assert user.role == "developer"
    assert user.is_active is False

    dev2 = await get_or_create_system_developer(async_db_session)
    assert dev2.id == dev.id
    assert dev2.user_id == dev.user_id


@pytest.mark.asyncio
async def test_extract_text_async_pdf():
    with patch("app.services.lead_intelligence.document_text.extract_text_pdfplumber", return_value="PDF text") as mock_pdf:
        text = await extract_text_async(b"pdf", "application/pdf")
    assert text == "PDF text"


@pytest.mark.asyncio
async def test_extract_text_async_html():
    text = await extract_text_async(b"<html><body>Hello</body></html>", "text/html")
    assert "Hello" in text



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



@pytest.mark.asyncio
async def test_get_or_create_pre_audit_workflow(async_db_session):
    from app.services.lead_intelligence.pre_audit_workflow import get_or_create_pre_audit_workflow

    wf = await get_or_create_pre_audit_workflow(async_db_session)
    assert wf.name == "pre_audit_document_package"
    wf2 = await get_or_create_pre_audit_workflow(async_db_session)
    assert wf2.id == wf.id



@pytest.mark.asyncio
async def test_pre_audit_runner_parses_output(async_db_session, convertible_lead):
    from app.services.lead_intelligence.pre_audit_runner import PreAuditRunner

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

        result = await runner.run_for_project(project, lead_id=str(convertible_lead.id))

    assert result.status == PreAuditStatusEnum.passed
    assert result.readiness_score == 0.85



class _FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.mark.asyncio
async def test_run_pre_audit_pipeline_task(async_db_session, convertible_lead):
    with patch(
        "app.tasks.pre_audit_jobs.AsyncSessionLocal",
        return_value=_FakeSessionContext(async_db_session),
    ):
        with patch("app.tasks.pre_audit_jobs.convert_lead_to_project") as mock_convert:
            mock_convert.delay = MagicMock()
            run_pre_audit_pipeline()
    # If no fetched docs, no conversion queued
    mock_convert.delay.assert_not_called()


@pytest.mark.asyncio
async def test_run_pre_audit_pipeline_pending_only(async_db_session):
    from app.models import LeadProjectStatusEnum

    pending_lead = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="PENDING-001",
        project_name="Pending Project",
        project_developer="Acme Carbon",
        methodology="TPDDTEC_v4",
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        lead_status=LeadWorkflowStatusEnum.qualified,
        status=LeadProjectStatusEnum.under_validation,
    )
    registered_lead = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="REG-001",
        project_name="Registered Project",
        project_developer="Acme Carbon",
        methodology="TPDDTEC_v4",
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        lead_status=LeadWorkflowStatusEnum.qualified,
        status=LeadProjectStatusEnum.registered,
    )
    pending_doc = LeadDocument(
        lead=pending_lead,
        document_type="pdd",
        source_url="https://example.com/pending.pdf",
        mime_type="application/pdf",
        s3_key="leads/cdm/pending/pdd.pdf",
        s3_bucket="bucket",
        file_size_bytes=1234,
        file_hash_sha256="abcd",
        status=LeadDocumentStatusEnum.fetched,
    )
    registered_doc = LeadDocument(
        lead=registered_lead,
        document_type="pdd",
        source_url="https://example.com/registered.pdf",
        mime_type="application/pdf",
        s3_key="leads/cdm/registered/pdd.pdf",
        s3_bucket="bucket",
        file_size_bytes=1234,
        file_hash_sha256="abcd",
        status=LeadDocumentStatusEnum.fetched,
    )
    async_db_session.add_all([pending_lead, registered_lead, pending_doc, registered_doc])
    await async_db_session.commit()

    with patch(
        "app.tasks.pre_audit_jobs.AsyncSessionLocal",
        return_value=_FakeSessionContext(async_db_session),
    ):
        with patch("app.tasks.pre_audit_jobs.convert_lead_to_project") as mock_convert:
            mock_convert.delay = MagicMock()
            with patch("app.tasks.pre_audit_jobs.settings.PRE_AUDIT_PENDING_ONLY", True):
                run_pre_audit_pipeline()

    queued_ids = [call[0][0] for call in mock_convert.delay.call_args_list]
    assert str(pending_lead.id) in queued_ids
    assert str(registered_lead.id) not in queued_ids


@pytest.mark.asyncio
async def test_fetch_lead_documents_updates_fingerprint(async_db_session):
    from app.tasks.pre_audit_jobs import fetch_lead_documents

    lead = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="FP-001",
        project_name="Fingerprint Lead",
        lead_status=LeadWorkflowStatusEnum.new,
    )
    doc = LeadDocument(
        lead=lead,
        document_type="pdd",
        source_url="https://example.com/pdd.pdf",
        status=LeadDocumentStatusEnum.discovered,
    )
    async_db_session.add_all([lead, doc])
    await async_db_session.commit()
    await async_db_session.refresh(lead)

    with patch(
        "app.tasks.pre_audit_jobs.AsyncSessionLocal",
        return_value=_FakeSessionContext(async_db_session),
    ):
        with patch("app.tasks.pre_audit_jobs.get_scraper") as mock_factory:
            mock_scraper = MagicMock()
            mock_scraper.fetch_documents.return_value = [
                {
                    "document_type": "pdd",
                    "source_url": "https://example.com/pdd.pdf",
                    "title": "PDD",
                }
            ]
            mock_scraper.close = MagicMock()
            mock_factory.return_value = mock_scraper

            with patch("app.tasks.pre_audit_jobs.RegistryDocumentFetcher") as MockFetcher:
                async def _fake_fetch(document, lead_id, registry_source):
                    document.status = LeadDocumentStatusEnum.fetched
                    document.file_hash_sha256 = "abc123"
                    return document

                mock_fetcher = MagicMock()
                mock_fetcher.fetch_document = AsyncMock(side_effect=_fake_fetch)
                mock_fetcher.close = AsyncMock()
                MockFetcher.return_value = mock_fetcher

                fetch_lead_documents(str(lead.id))

    await async_db_session.refresh(lead)
    expected = hashlib.sha256("https://example.com/pdd.pdf|abc123".encode("utf-8")).hexdigest()
    assert lead.document_fingerprint == expected


@pytest.mark.asyncio
async def test_re_audit_changed_projects(async_db_session):
    from app.tasks.pre_audit_jobs import re_audit_changed_projects

    developer = await get_or_create_system_developer(async_db_session)

    lead = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="RE-001",
        project_name="Re-audit Lead",
        lead_status=LeadWorkflowStatusEnum.converted,
        status=LeadProjectStatusEnum.under_validation,
    )
    project = Project(
        name="Re-audit Project",
        developer_id=developer.id,
        methodology=MethodologyEnum.TPDDTEC_v4,
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        status=ProjectStatusEnum.onboarding,
    )
    async_db_session.add(project)
    await async_db_session.flush()
    lead.converted_project_id = project.id
    doc = LeadDocument(
        lead=lead,
        document_type="pdd",
        source_url="https://example.com/pdd.pdf",
        status=LeadDocumentStatusEnum.fetched,
        file_hash_sha256="oldhash",
    )
    async_db_session.add_all([lead, doc])
    await async_db_session.commit()

    with patch(
        "app.tasks.pre_audit_jobs.AsyncSessionLocal",
        return_value=_FakeSessionContext(async_db_session),
    ):
        with patch("app.tasks.pre_audit_jobs.run_pre_audit_for_project") as mock_preaudit:
            mock_preaudit.delay = MagicMock()
            re_audit_changed_projects()

    mock_preaudit.delay.assert_called_once_with(str(project.id), lead_id=str(lead.id))
    await async_db_session.refresh(lead)
    assert lead.document_fingerprint is not None



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


class _FakeKimiAPIClient:
    """Deterministic AI client that returns a passing pre-audit JSON response."""

    async def chat_completion(self, messages, temperature=0.3, max_tokens=2048):
        return {
            "success": True,
            "content": json.dumps({
                "score": 0.85,
                "passed": True,
                "reasoning": "Documents are complete and consistent. No gaps identified.",
                "recommendation": "Ready for auditor assignment.",
            }),
            "usage": {},
        }


@pytest.mark.asyncio
async def test_pre_audit_runner_end_to_end(async_db_session):
    """Create a lead, convert it, and run the real pre-audit workflow with mocked AI/S3."""
    lead = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="E2E-001",
        project_name="End-to-End Project",
        project_developer="Acme Carbon",
        methodology="TPDDTEC_v4",
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        lead_status=LeadWorkflowStatusEnum.qualified,
    )
    doc = LeadDocument(
        document_type="pdd",
        source_url="https://example.com/pdd.html",
        mime_type="text/html",
        s3_key="leads/cdm/e2e/pdd.html",
        s3_bucket="bucket",
        file_size_bytes=1234,
        file_hash_sha256="abcd",
        status=LeadDocumentStatusEnum.fetched,
    )
    lead.documents = [doc]
    async_db_session.add(lead)
    await async_db_session.commit()
    await async_db_session.refresh(lead)

    converter = LeadToProjectConverter(async_db_session)
    project = await converter.convert(lead)

    runner = PreAuditRunner(async_db_session)
    with patch("app.services.lead_intelligence.pre_audit_runner.fetch_s3_bytes", new_callable=AsyncMock, return_value=b"<html><body>PDD content</body></html>"), \
         patch("app.services.kimi_api.KimiAPIClient", _FakeKimiAPIClient), \
         patch("app.database.AsyncSessionLocal", return_value=_FakeSessionContext(async_db_session)):
        pre_audit = await runner.run_for_project(project, lead_id=str(lead.id))

    assert isinstance(pre_audit, ProjectPreAudit)
    assert pre_audit.project_id == project.id
    assert pre_audit.status == PreAuditStatusEnum.passed
    assert pre_audit.readiness_score == pytest.approx(0.85)
    assert pre_audit.gap_summary["gaps"] == []
    assert pre_audit.gap_summary["risk_flags"] == []
    assert "Ready for auditor" in pre_audit.gap_summary["recommendation"]



@pytest.mark.asyncio
async def test_bulk_import_leads_creates_and_queues_fetch(client: AsyncClient, operator_headers, async_db_session):
    payload = {
        "registry_source": "cdm",
        "items": [
            {"external_id": "BULK-001", "project_name": "Bulk Project 1"},
            {"external_id": "BULK-002", "registry_url": "https://cdm.unfccc.int/BULK-002"},
        ],
    }
    with patch("app.api.leads.fetch_lead_documents_task") as mock_fetch:
        mock_fetch.delay = MagicMock()
        resp = await client.post("/leads/bulk-import", json=payload, headers=operator_headers)

    assert resp.status_code == 202
    data = resp.json()
    assert data["registry_source"] == "cdm"
    assert data["created"] == 2
    assert data["updated"] == 0
    assert data["queued"] == 2
    assert data["errors"] == 0
    assert len(data["leads"]) == 2
    assert mock_fetch.delay.call_count == 2


@pytest.mark.asyncio
async def test_bulk_import_leads_rejects_invalid_registry(client: AsyncClient, operator_headers):
    payload = {
        "registry_source": "not_a_registry",
        "items": [{"external_id": "BULK-003"}],
    }
    resp = await client.post("/leads/bulk-import", json=payload, headers=operator_headers)
    assert resp.status_code == 400
    assert "Invalid registry_source" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_bulk_import_leads_updates_existing(client: AsyncClient, operator_headers, async_db_session):
    existing = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="BULK-004",
        project_name="Old Name",
        lead_status=LeadWorkflowStatusEnum.new,
    )
    async_db_session.add(existing)
    await async_db_session.commit()
    await async_db_session.refresh(existing)

    payload = {
        "registry_source": "cdm",
        "items": [{"external_id": "BULK-004", "project_name": "Updated Name"}],
    }
    with patch("app.api.leads.fetch_lead_documents_task") as mock_fetch:
        mock_fetch.delay = MagicMock()
        resp = await client.post("/leads/bulk-import", json=payload, headers=operator_headers)

    assert resp.status_code == 202
    data = resp.json()
    assert data["created"] == 0
    assert data["updated"] == 1
    assert data["queued"] == 1
    await async_db_session.refresh(existing)
    assert existing.project_name == "Updated Name"



@pytest.mark.asyncio
async def test_list_pending_opportunities(client: AsyncClient, operator_headers, async_db_session):
    pending = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="OPP-001",
        project_name="Pending Opportunity",
        status=LeadProjectStatusEnum.under_validation,
        lead_status=LeadWorkflowStatusEnum.qualified,
        stuck_score=75.0,
    )
    registered = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="OPP-002",
        project_name="Registered Opportunity",
        status=LeadProjectStatusEnum.registered,
        lead_status=LeadWorkflowStatusEnum.qualified,
        stuck_score=95.0,
    )
    doc = LeadDocument(
        lead=pending,
        document_type="pdd",
        source_url="https://example.com/pdd.pdf",
        status=LeadDocumentStatusEnum.fetched,
    )
    async_db_session.add_all([pending, registered, doc])
    await async_db_session.commit()

    resp = await client.get("/leads/opportunities/pending", headers=operator_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["external_id"] == "OPP-001"
    assert data[0]["document_count"] == 1
    assert data[0]["fetched_document_count"] == 1


@pytest.mark.asyncio
async def test_list_pending_opportunities_filter_by_source(client: AsyncClient, operator_headers, async_db_session):
    cdm_lead = Lead(
        registry_source=LeadRegistrySourceEnum.cdm,
        external_id="OPP-003",
        project_name="CDM Opportunity",
        status=LeadProjectStatusEnum.under_validation,
        lead_status=LeadWorkflowStatusEnum.new,
        stuck_score=50.0,
    )
    verra_lead = Lead(
        registry_source=LeadRegistrySourceEnum.verra,
        external_id="OPP-004",
        project_name="Verra Opportunity",
        status=LeadProjectStatusEnum.under_validation,
        lead_status=LeadWorkflowStatusEnum.new,
        stuck_score=60.0,
    )
    async_db_session.add_all([cdm_lead, verra_lead])
    await async_db_session.commit()

    resp = await client.get("/leads/opportunities/pending?registry_source=verra", headers=operator_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["external_id"] == "OPP-004"
