from unittest.mock import patch
from sqlalchemy import select
import pytest

from app.models import User
from app.services.lead_intelligence.system_developer import (
    SYSTEM_COMPANY_NAME,
    SYSTEM_DEVELOPER_EMAIL,
    get_or_create_system_developer,
)
from app.services.lead_intelligence.document_text import extract_text_async


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
