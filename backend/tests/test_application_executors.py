"""Tests for the AI application pipeline validation executors."""

import uuid
from contextlib import asynccontextmanager

import pytest

from app.validation_engine.models import WorkflowStepType


@pytest.fixture
def patch_db_context(db_session, monkeypatch):
    """Route app.database.get_db_context to the test session.

    Executors import get_db_context at call time, so monkeypatching the
    app.database module attribute is picked up. Without this, executors
    would open sessions on the app's own engine (a separate empty SQLite
    in-memory database in tests).
    """

    @asynccontextmanager
    async def _ctx():
        yield db_session

    monkeypatch.setattr("app.database.get_db_context", _ctx)


def test_application_step_types_exist():
    assert WorkflowStepType.application_intake.value == "application_intake"
    assert WorkflowStepType.document_collection.value == "document_collection"
    assert WorkflowStepType.document_ai_classification.value == "document_ai_classification"


@pytest.mark.asyncio
async def test_application_intake_executor(db_session, patch_db_context):
    from app.validation_engine.executors import ApplicationIntakeExecutor
    from app.validation_engine.schemas import ApplicationIntakeConfig
    from app.validation_engine.models import ValidationRun

    executor = ApplicationIntakeExecutor()
    config = ApplicationIntakeConfig(
        applicant_email="owner@example.com",
        project_title="Test Project",
        country="Kenya",
        sector="cookstoves",
    ).model_dump()
    run = ValidationRun(id=uuid.uuid4())

    result = await executor.execute(config, {}, run)

    assert result["project_title"] == "Test Project"
    assert result["status"] == "intake"
    assert "application_id" in result
