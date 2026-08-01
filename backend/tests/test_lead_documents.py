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
