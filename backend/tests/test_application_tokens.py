import uuid

import pytest

from app.services.application_tokens import (
    create_applicant_token,
    verify_applicant_token,
)


@pytest.mark.asyncio
async def test_applicant_token_roundtrip():
    app_id = uuid.uuid4()
    token = create_applicant_token(app_id)
    assert isinstance(token, str)
    verified = verify_applicant_token(token)
    assert verified == app_id
