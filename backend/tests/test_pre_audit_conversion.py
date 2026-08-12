from datetime import date
from unittest.mock import patch, AsyncMock
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import (
    Lead,
    LeadDocument,
    LeadDocumentStatusEnum,
    LeadRegistrySourceEnum,
    LeadWorkflowStatusEnum,
    User,
)
from app.services.lead_intelligence.document_text import extract_text_async
from app.services.lead_intelligence.lead_converter import LeadToProjectConverter, LeadConversionError
from app.services.lead_intelligence.system_developer import (
    SYSTEM_COMPANY_NAME,
    SYSTEM_DEVELOPER_EMAIL,
    get_or_create_system_developer,
)


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
