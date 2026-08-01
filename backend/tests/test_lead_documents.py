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

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock

from app.models import Lead, LeadDocument, LeadDocumentStatusEnum, LeadRegistrySourceEnum
from app.services.lead_intelligence.document_fetcher import RegistryDocumentFetcher
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
    with patch.object(fetcher.client, "get") as mock_get:
        mock_get.side_effect = Exception("connection refused")

        result = await fetcher.fetch_document(doc)

    assert result.status == LeadDocumentStatusEnum.failed
    assert "connection refused" in result.error_message
    fetcher.close()


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
