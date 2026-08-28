import pytest
from sqlalchemy import select
from app.models import Application, ApplicationStatusEnum


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
