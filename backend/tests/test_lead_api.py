"""Tests for Lead Intelligence API.

NOTE: These tests require auth fixtures that are not yet set up in the test suite.
They are skipped until auth fixtures are available.
"""

import pytest
import uuid

pytestmark = pytest.mark.skip(reason="Auth fixtures not available in test suite")


@pytest.fixture
async def sample_lead(client, auth_headers):
    payload = {
        "registry_source": "manual",
        "external_id": "TEST-001",
        "project_name": "Test Lead Project",
        "project_developer": "Test Developer",
        "country": "Kenya",
        "methodology": "VM0050",
        "status": "under_verification",
        "stuck_score": 65.0,
        "priority": "high",
    }
    res = await client.post("/leads/", json=payload, headers=auth_headers)
    assert res.status_code == 201
    return res.json()


class TestListLeads:
    @pytest.mark.asyncio
    async def test_list_leads(self, client, auth_headers):
        res = await client.get("/leads/", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_filter_by_priority(self, client, auth_headers):
        res = await client.get("/leads/?priority=high", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert all(l["priority"] == "high" for l in data)

    @pytest.mark.asyncio
    async def test_filter_by_country(self, client, auth_headers):
        res = await client.get("/leads/?country=Kenya", headers=auth_headers)
        assert res.status_code == 200


class TestCreateLead:
    @pytest.mark.asyncio
    async def test_create_lead(self, client, auth_headers):
        payload = {
            "registry_source": "manual",
            "external_id": "TEST-002",
            "project_name": "New Test Lead",
            "country": "Ghana",
            "methodology": "AMS-II.G",
            "status": "registered",
        }
        res = await client.post("/leads/", json=payload, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["project_name"] == "New Test Lead"
        assert data["id"] is not None


class TestUpdateLead:
    @pytest.mark.asyncio
    async def test_update_lead_status(self, client, auth_headers, sample_lead):
        lead_id = sample_lead["id"]
        res = await client.patch(
            f"/leads/{lead_id}",
            json={"lead_status": "contacted", "notes": "Called developer"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["lead_status"] == "contacted"
        assert data["notes"] == "Called developer"


class TestDeleteLead:
    @pytest.mark.asyncio
    async def test_delete_lead(self, client, admin_auth_headers, sample_lead):
        lead_id = sample_lead["id"]
        res = await client.delete(f"/leads/{lead_id}", headers=admin_auth_headers)
        assert res.status_code == 204


class TestLeadStats:
    @pytest.mark.asyncio
    async def test_get_stats(self, client, auth_headers):
        res = await client.get("/leads/stats/dashboard", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "total_leads" in data
        assert "avg_stuck_score" in data
        assert "by_registry" in data
