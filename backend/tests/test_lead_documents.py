import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock, Mock

from app.models import Lead, LeadDocument, LeadDocumentStatusEnum, LeadRegistrySourceEnum
from app.services.lead_intelligence.document_fetcher import RegistryDocumentFetcher
from app.tasks.pre_audit_jobs import fetch_lead_documents
from app.services.lead_intelligence.cdm import _parse_cdm_documents
from app.services.lead_intelligence.gold_standard import _parse_gold_standard_documents
from app.services.lead_intelligence.verra import _parse_verra_documents


@pytest_asyncio.fixture
async def sample_lead(async_db_session):
    lead = Lead(
        registry_source=LeadRegistrySourceEnum.manual,
        external_id="SAMPLE-001",
        project_name="Sample Lead Project",
    )
    async_db_session.add(lead)
    await async_db_session.commit()
    await async_db_session.refresh(lead)
    return lead


@pytest.mark.asyncio
async def test_get_lead_documents_empty(client: AsyncClient, operator_headers):
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
async def test_get_lead_documents_missing_lead(client: AsyncClient, operator_headers):
    resp = await client.get("/leads/00000000-0000-0000-0000-000000000000/documents", headers=operator_headers)
    assert resp.status_code == 404


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


class _FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.mark.asyncio
async def test_fetch_lead_documents_task(async_db_session, sample_lead):
    with patch(
        "app.tasks.pre_audit_jobs.AsyncSessionLocal",
        return_value=_FakeSessionContext(async_db_session),
    ):
        with patch("app.tasks.pre_audit_jobs.get_scraper") as mock_factory:
            mock_scraper = MagicMock()
            mock_scraper.fetch_documents.return_value = [
                {"document_type": "pdd", "source_url": "https://example.com/pdd.pdf", "title": "PDD"}
            ]
            mock_scraper.close = MagicMock()
            mock_factory.return_value = mock_scraper

            with patch("app.tasks.pre_audit_jobs.RegistryDocumentFetcher") as MockFetcher:
                mock_fetcher = MagicMock()
                mock_fetcher.fetch_document = AsyncMock(return_value=MagicMock())
                mock_fetcher.close = AsyncMock()
                MockFetcher.return_value = mock_fetcher

                fetch_lead_documents(str(sample_lead.id))

    mock_scraper.fetch_documents.assert_called_once()
    mock_fetcher.fetch_document.assert_called_once()


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

    mock_scanner = MagicMock()
    mock_scanner.scan_buffer = AsyncMock(return_value=MagicMock(status="clean"))

    fetcher = RegistryDocumentFetcher()
    with patch.object(fetcher.client, "get", new_callable=AsyncMock) as mock_get, \
         patch.object(fetcher, "_upload_to_s3", new_callable=AsyncMock) as mock_upload, \
         patch("app.services.lead_intelligence.document_fetcher.get_scanner", return_value=mock_scanner):
        mock_response = MagicMock()
        mock_response.content = b"PDF content"
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        mock_upload.return_value = None

        result = await fetcher.fetch_document(
            doc,
            lead_id=str(sample_lead.id),
            registry_source=sample_lead.registry_source.value,
        )

    assert result.status == LeadDocumentStatusEnum.fetched
    assert result.file_hash_sha256 is not None
    assert result.mime_type == "application/pdf"
    assert result.fetch_attempts == 1
    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_document_failure(async_db_session, sample_lead):
    doc = LeadDocument(
        lead_id=sample_lead.id,
        document_type="monitoring_report",
        source_url="https://example.com/report.pdf",
    )
    async_db_session.add(doc)
    await async_db_session.commit()
    await async_db_session.refresh(doc)

    fetcher = RegistryDocumentFetcher()
    with patch.object(fetcher.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("connection refused")

        result = await fetcher.fetch_document(
            doc,
            lead_id=str(sample_lead.id),
            registry_source=sample_lead.registry_source.value,
        )

    assert result.status == LeadDocumentStatusEnum.failed
    assert "connection refused" in result.error_message
    assert result.fetch_attempts == 1
    await fetcher.close()


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
