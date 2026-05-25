import uuid
import pytest
from datetime import datetime, timezone



class TestConsentAPI:
    @pytest.mark.asyncio
    async def test_record_and_get_consent(self, authenticated_client):
        client, user = authenticated_client
        response = await client.post(
            "/compliance/consent",
            json={
                "subject_id": "HH-001",
                "subject_type": "household",
                "consent_type": "data_processing",
                "granted": True,
                "method": "explicit",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["granted"] is True

        response = await client.get("/compliance/consent/HH-001")
        assert response.status_code == 200
        data = response.json()
        assert data["has_consent"] is True
        assert data["latest_record"]["type"] == "data_processing"

    @pytest.mark.asyncio
    async def test_revoke_consent(self, authenticated_client):
        client, user = authenticated_client
        await client.post(
            "/compliance/consent",
            json={
                "subject_id": "HH-002",
                "subject_type": "household",
                "consent_type": "data_processing",
                "granted": True,
            },
        )
        await client.post(
            "/compliance/consent",
            json={
                "subject_id": "HH-002",
                "subject_type": "household",
                "consent_type": "data_processing",
                "granted": False,
            },
        )

        response = await client.get("/compliance/consent/HH-002")
        data = response.json()
        assert data["has_consent"] is False


class TestDSRAPI:
    @pytest.mark.asyncio
    async def test_submit_dsr(self, authenticated_client):
        client, user = authenticated_client
        response = await client.post(
            "/compliance/dsr",
            json={
                "request_type": "access",
                "subject_id": "HH-001",
                "subject_type": "household",
                "description": "I want to see my data",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "received"
        assert "sla_deadline" in data

    @pytest.mark.asyncio
    async def test_dsr_sla_tracking(self, authenticated_client):
        client, user = authenticated_client
        response = await client.post(
            "/compliance/dsr",
            json={
                "request_type": "erasure",
                "subject_id": "HH-003",
                "subject_type": "household",
            },
        )
        data = response.json()
        deadline_str = data["sla_deadline"]
        if deadline_str.endswith("Z"):
            deadline_str = deadline_str[:-1] + "+00:00"
        deadline = datetime.fromisoformat(deadline_str)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        assert (deadline - now).days <= 30


class TestBreachAPI:
    @pytest.mark.asyncio
    async def test_report_breach(self, authenticated_client):
        client, user = authenticated_client
        response = await client.post(
            "/compliance/breach",
            json={
                "title": "Test Breach",
                "description": "Unauthorized access detected",
                "severity": "high",
                "affected_subjects_count": 50,
                "affected_data_types": ["photos", "gps"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "detected"
        assert data["sla_hours_remaining"] == 72

    @pytest.mark.asyncio
    async def test_breach_status_update(self, authenticated_client):
        client, user = authenticated_client
        create_resp = await client.post(
            "/compliance/breach",
            json={
                "title": "Test Breach 2",
                "description": "Test",
                "severity": "medium",
            },
        )
        breach_id = create_resp.json()["id"]

        update_resp = await client.patch(
            f"/compliance/breach/{breach_id}",
            json={"status": "contained", "containment_measures": "Access revoked"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "contained"


class TestConflictOfInterest:
    @pytest.mark.asyncio
    async def test_disclose_conflict(self, authenticated_client):
        client, user = authenticated_client
        response = await client.post(
            "/compliance/conflict-of-interest",
            json={
                "project_id": str(uuid.uuid4()),
                "relationship_type": "financial",
                "description": "I own shares in the developer company",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Disclosure submitted for review"

    @pytest.mark.asyncio
    async def test_independence_check_blocks_pdd(self, authenticated_client):
        client, user = authenticated_client
        project_id = str(uuid.uuid4())
        response = await client.get(
            f"/compliance/independence/check/{project_id}",
            params={"action": "draft_pdd"},
        )
        data = response.json()
        assert data["allowed"] is False
        assert "PDD drafting is restricted" in data["reason"]

    @pytest.mark.asyncio
    async def test_independence_check_allows_other(self, authenticated_client):
        client, user = authenticated_client
        project_id = str(uuid.uuid4())
        response = await client.get(
            f"/compliance/independence/check/{project_id}",
            params={"action": "view_report"},
        )
        data = response.json()
        assert data["allowed"] is True


class TestMethodologyVersioning:
    @pytest.mark.asyncio
    async def test_create_and_list_methodology(self, authenticated_client):
        client, user = authenticated_client
        response = await client.post(
            "/compliance/methodology",
            json={
                "methodology_name": "TPDDTEC_v4",
                "version": "4.2.1",
                "effective_date": "2024-01-01",
                "rules_json": {"min_sample_size": 30},
                "change_summary": "Updated sample size requirement",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["version"] == "4.2.1"

        list_resp = await client.get("/compliance/methodology")
        assert list_resp.status_code == 200
        versions = list_resp.json()
        assert any(v["version"] == "4.2.1" for v in versions)
