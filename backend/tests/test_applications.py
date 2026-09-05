import pytest
from sqlalchemy import select
from app.models import Application, ApplicationStatusEnum
from app.schemas import ApplicationCreate, ApplicationOut


@pytest.mark.asyncio
async def test_application_model_exists(client, db_session):
    app = Application(
        applicant_email_hash="test@example.com",
        project_title="Test Stove Project",
        country="Kenya",
        sector="cookstoves",
        status=ApplicationStatusEnum.intake,
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    result = await db_session.execute(select(Application).where(Application.id == app.id))
    fetched = result.scalar_one()
    assert fetched.project_title == "Test Stove Project"
    assert fetched.status == ApplicationStatusEnum.intake


def test_application_schema_roundtrip():
    data = {
        "applicant_email_hash": "test@example.com",
        "project_title": "Test",
        "country": "Kenya",
        "sector": "cookstoves",
        "status": "intake",
    }
    created = ApplicationCreate.model_validate(data)
    assert created.project_title == "Test"


@pytest.mark.asyncio
async def test_create_application(client, db_session):
    payload = {
        "applicant_email": "dev@example.com",
        "project_title": "Kenya Cookstoves",
        "country": "Kenya",
        "sector": "cookstoves",
    }
    response = await client.post("/applications", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["project_title"] == "Kenya Cookstoves"
    assert data["status"] == "intake"
    assert "applicant_token" in data
