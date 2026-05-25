"""Tests for request ID middleware."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


class TestRequestID:
    @pytest.mark.asyncio
    async def test_request_id_generated(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
            assert response.status_code == 200
            assert "X-Request-ID" in response.headers
            assert len(response.headers["X-Request-ID"]) == 36  # UUID length

    @pytest.mark.asyncio
    async def test_request_id_propagated(self):
        custom_id = "test-request-id-123"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/", headers={"X-Request-ID": custom_id})
            assert response.status_code == 200
            assert response.headers["X-Request-ID"] == custom_id
