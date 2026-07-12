import pytest
import uuid


@pytest.mark.asyncio
async def test_create_and_get_generated_methodology(authenticated_client):
    client, user = authenticated_client
    payload = {
        "project_id": "36f38264-ae57-4794-bfaf-e2ac5a37720a",
        "name": "Blue Carbon Macroalgae",
        "sector": "Blue Carbon",
        "activity_description": "Cultivating macroalgae to sequester carbon in deep ocean sediments.",
        "boundaries": {"geographic": "Kenya EEZ", "temporal": "2025-2045"},
        "data_sources": [{"type": "satellite", "frequency": "monthly"}],
    }
    r = await client.post("/methodology-generator/", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == payload["name"]
    assert data["status"] == "draft"

    r2 = await client.get(f"/methodology-generator/{data['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == data["id"]


@pytest.mark.asyncio
async def test_list_generated_methodologies(authenticated_client):
    client, _ = authenticated_client
    r = await client.get("/methodology-generator/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_invalid_status_transition(authenticated_client):
    client, _ = authenticated_client
    payload = {
        "project_id": "36f38264-ae57-4794-bfaf-e2ac5a37720a",
        "name": "Test Transition",
        "sector": "Test",
        "activity_description": "A test activity for status transition validation.",
        "boundaries": {},
        "data_sources": [],
    }
    r = await client.post("/methodology-generator/", json=payload)
    gm_id = r.json()["id"]
    r2 = await client.patch(
        f"/methodology-generator/{gm_id}/status",
        json={"status": "approved"},
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_status_transition_under_review_to_approved(authenticated_client):
    client, _ = authenticated_client
    payload = {
        "project_id": "36f38264-ae57-4794-bfaf-e2ac5a37720a",
        "name": "Test Approve",
        "sector": "Test",
        "activity_description": "A test activity for approval transition.",
        "boundaries": {},
        "data_sources": [],
    }
    r = await client.post("/methodology-generator/", json=payload)
    gm_id = r.json()["id"]

    r2 = await client.patch(
        f"/methodology-generator/{gm_id}/status",
        json={"status": "under_review"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "under_review"

    r3 = await client.patch(
        f"/methodology-generator/{gm_id}/status",
        json={"status": "approved"},
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_service_parse_json_response():
    from app.services.methodology_generator import MethodologyGeneratorService

    svc = MethodologyGeneratorService()
    content = '```json\n{"fits_existing_methodology": false}\n```'
    parsed = svc._parse_json_response(content)
    assert parsed["fits_existing_methodology"] is False
