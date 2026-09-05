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


# ─── Phase 2: applicant upload, portal, trigger, email ─────────────────────────


def _mock_clean_scanner(monkeypatch):
    """Patch the ClamAV scanner used by the applicant upload endpoint."""
    from unittest.mock import AsyncMock, MagicMock

    import app.services.clamav_scanner as clamav_module

    mock_scanner = MagicMock()
    mock_scanner.scan_buffer = AsyncMock(return_value=MagicMock(status="clean"))
    monkeypatch.setattr(clamav_module, "get_scanner", lambda: mock_scanner)
    return mock_scanner


@pytest.mark.asyncio
async def test_upload_document_with_applicant_token(client, db_session, sample_application, monkeypatch):
    from unittest.mock import patch

    from app.config import get_settings
    from app.services.application_tokens import create_applicant_token

    monkeypatch.setattr(get_settings(), "S3_BUCKET_NAME", "test-bucket")
    _mock_clean_scanner(monkeypatch)

    token = create_applicant_token(sample_application.id)
    with patch("app.services.s3.upload_bytes", return_value=None):
        response = await client.post(
            f"/applications/{sample_application.id}/documents",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("pdd-notes.txt", b"Project design document for improved cookstoves.", "text/plain")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "pdd-notes.txt"
    assert data["status"] == "fetched"
    assert data["source_type"] == "upload"
    assert "Project design document" in (data["extracted_text"] or "")


@pytest.mark.asyncio
async def test_upload_document_rejects_invalid_token(client, db_session, sample_application):
    response = await client.post(
        f"/applications/{sample_application.id}/documents",
        headers={"Authorization": "Bearer not-a-real-token"},
        files={"file": ("doc.txt", b"content", "text/plain")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_document_rejects_mismatched_token(client, db_session, sample_application):
    import uuid as uuidlib

    from app.services.application_tokens import create_applicant_token

    other_token = create_applicant_token(uuidlib.uuid4())
    response = await client.post(
        f"/applications/{sample_application.id}/documents",
        headers={"Authorization": f"Bearer {other_token}"},
        files={"file": ("doc.txt", b"content", "text/plain")},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_applicant_portal_returns_status_and_gaps(client, db_session, sample_application):
    from app.services.application_tokens import create_applicant_token

    sample_application.gap_findings = {
        "required_document_types": ["pdd"],
        "missing_document_types": ["pdd"],
        "has_gaps": True,
        "remediation": [{"document_type": "pdd", "guidance": "Upload the Project Design Document (PDD)."}],
    }
    await db_session.commit()

    token = create_applicant_token(sample_application.id)
    response = await client.get(
        f"/applications/{sample_application.id}/portal",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["application_id"] == str(sample_application.id)
    assert data["status"] == "intake"
    assert data["gap_findings"]["missing_document_types"] == ["pdd"]
    assert data["documents"] == []


@pytest.mark.asyncio
async def test_applicant_portal_requires_token(client, db_session, sample_application):
    response = await client.get(f"/applications/{sample_application.id}/portal")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_trigger_pipeline_creates_validation_run(client, authenticated_client, db_session):
    from unittest.mock import patch

    from sqlalchemy import select
    from app.validation_engine.models import ValidationRun

    intake_response = await client.post("/applications", json={
        "applicant_email": "owner@example.com",
        "project_title": "Kenya Stoves",
        "country": "Kenya",
        "sector": "cookstoves",
    })
    assert intake_response.status_code == 201
    app_id = intake_response.json()["id"]

    auth_client, _ = authenticated_client
    with patch("app.validation_engine.tasks.execute_validation_run") as mock_task:
        mock_task.delay.return_value = None
        response = await auth_client.post(f"/applications/{app_id}/trigger-pipeline")

    assert response.status_code == 200
    mock_task.delay.assert_called_once()

    # A ValidationRun was created and linked to the application
    run_result = await db_session.execute(select(ValidationRun))
    runs = run_result.scalars().all()
    assert len(runs) == 1
    assert runs[0].trigger_event == "application_pipeline"

    from app.models import Application
    application = await db_session.get(Application, __import__("uuid").UUID(app_id))
    assert application.validation_run_id == runs[0].id


@pytest.mark.asyncio
async def test_create_application_sends_welcome_email(client, db_session, monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    import app.services.email as email_module

    mock_service = MagicMock()
    mock_service.send_email = AsyncMock()
    monkeypatch.setattr(email_module, "get_email_service", lambda: mock_service)

    response = await client.post("/applications", json={
        "applicant_email": "owner@example.com",
        "project_title": "Kenya Stoves",
    })
    assert response.status_code == 201

    mock_service.send_email.assert_awaited_once()
    call_kwargs = mock_service.send_email.await_args.kwargs
    assert call_kwargs["to"] == "owner@example.com"
    assert "/apply/portal" in call_kwargs["body_text"]
