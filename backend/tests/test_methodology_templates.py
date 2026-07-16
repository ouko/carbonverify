import pytest
import uuid

from sqlalchemy import select

from app.models import MethodologyTemplate
from app.services.methodology_generator import MethodologyTemplateService
from scripts.seed_demo_data import seed_methodology_templates


@pytest.mark.asyncio
async def test_list_methodology_templates(authenticated_client, db_session):
    client, _ = authenticated_client
    db_session.add(
        MethodologyTemplate(
            id=uuid.uuid4(),
            name="Test Template",
            sector="Test",
            is_active=True,
            defaults_json={"boundaries": {}, "data_sources": []},
        )
    )
    await db_session.commit()

    r = await client.get("/methodology-templates/")
    assert r.status_code == 200
    data = r.json()
    assert any(t["name"] == "Test Template" for t in data)


@pytest.mark.asyncio
async def test_get_methodology_template(authenticated_client, db_session):
    client, _ = authenticated_client
    template_id = uuid.uuid4()
    db_session.add(
        MethodologyTemplate(
            id=template_id,
            name="Single Template",
            sector="Single",
            is_active=True,
            defaults_json={"boundaries": {}, "data_sources": []},
        )
    )
    await db_session.commit()

    r = await client.get(f"/methodology-templates/{template_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Single Template"


@pytest.mark.asyncio
async def test_get_inactive_template_returns_404(authenticated_client, db_session):
    client, _ = authenticated_client
    template_id = uuid.uuid4()
    db_session.add(
        MethodologyTemplate(
            id=template_id,
            name="Inactive Template",
            sector="Inactive",
            is_active=False,
            defaults_json={"boundaries": {}, "data_sources": []},
        )
    )
    await db_session.commit()

    r = await client.get(f"/methodology-templates/{template_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_service_defaults_to_form_handles_malformed_json():
    service = MethodologyTemplateService()
    template = MethodologyTemplate(
        id=uuid.uuid4(),
        name="Malformed",
        sector="Malformed",
        is_active=True,
        defaults_json={"boundaries": "not-a-dict", "data_sources": "not-a-list"},
    )
    result = service.defaults_to_form(template)
    assert result["sector"] == "Malformed"
    assert result["boundaries"] == {
        "geographic_scope": "",
        "temporal_scope": "",
        "physical_boundary": "",
        "ghg_sources_included": "",
    }
    assert result["data_sources"] == []


@pytest.mark.asyncio
async def test_seed_methodology_templates_is_idempotent(db_session):
    """Calling seed_methodology_templates twice must not duplicate templates."""
    await seed_methodology_templates(db_session)
    result = await db_session.execute(select(MethodologyTemplate))
    count_after_first = len(result.scalars().all())

    await seed_methodology_templates(db_session)
    result = await db_session.execute(select(MethodologyTemplate))
    count_after_second = len(result.scalars().all())

    assert count_after_first > 0
    assert count_after_second == count_after_first
