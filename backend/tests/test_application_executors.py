"""Tests for the AI application pipeline validation executors."""

import uuid

import pytest
import pytest_asyncio

from app.validation_engine.models import WorkflowStepType


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


@pytest.mark.asyncio
async def test_document_collection_executor(db_session, patch_db_context, sample_application):
    from app.validation_engine.executors import DocumentCollectionExecutor
    from app.validation_engine.schemas import DocumentCollectionConfig
    from app.validation_engine.models import ValidationRun

    executor = DocumentCollectionExecutor()
    config = DocumentCollectionConfig(
        sources=[{"type": "upload", "folder_id": None}],
        required_document_types=["pdd"],
    ).model_dump()
    run = ValidationRun(id=uuid.uuid4())
    context = {"application_id": str(sample_application.id)}

    result = await executor.execute(config, context, run)

    assert "collected_documents" in result
    assert result["status"] == "awaiting_documents"
    assert len(result["collected_documents"]) == 1


@pytest_asyncio.fixture
async def sample_document(db_session, sample_application):
    from app.models import (
        ApplicationDocument,
        ApplicationDocumentSourceEnum,
        ApplicationDocumentStatusEnum,
    )

    document = ApplicationDocument(
        application_id=sample_application.id,
        source_type=ApplicationDocumentSourceEnum.upload,
        original_filename="project-doc.pdf",
        status=ApplicationDocumentStatusEnum.fetched,
        extracted_text="Project design document for improved cookstoves.",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


@pytest.mark.asyncio
async def test_document_ai_classification_executor(db_session, patch_db_context, sample_document):
    from app.validation_engine.executors import DocumentAiClassificationExecutor
    from app.validation_engine.schemas import DocumentAiClassificationConfig
    from app.validation_engine.models import ValidationRun

    executor = DocumentAiClassificationExecutor()
    config = DocumentAiClassificationConfig(classify_with_kimi=False).model_dump()
    run = ValidationRun(id=uuid.uuid4())
    context = {"application_id": str(sample_document.application_id)}

    result = await executor.execute(config, context, run)

    assert "classified_documents" in result
    assert result["classified_documents"][0]["document_type"] == "other"


def test_application_executors_registered():
    from app.validation_engine.executors import StepExecutorRegistry

    registry = StepExecutorRegistry()
    assert registry.get_executor(WorkflowStepType.application_intake) is not None
    assert registry.get_executor(WorkflowStepType.document_collection) is not None
    assert registry.get_executor(WorkflowStepType.document_ai_classification) is not None


@pytest.mark.asyncio
async def test_intake_executor_returns_existing_application(db_session, patch_db_context, sample_application):
    from sqlalchemy import func, select
    from app.models import Application
    from app.validation_engine.executors import ApplicationIntakeExecutor
    from app.validation_engine.schemas import ApplicationIntakeConfig
    from app.validation_engine.models import ValidationRun

    executor = ApplicationIntakeExecutor()
    config = ApplicationIntakeConfig(
        applicant_email="owner@example.com",
        project_title="Sample Project",
    ).model_dump()
    run = ValidationRun(id=uuid.uuid4())
    context = {"input": {"application_id": str(sample_application.id)}}

    result = await executor.execute(config, context, run)

    assert result["existing"] is True
    assert result["application_id"] == str(sample_application.id)
    # No duplicate application created
    count = await db_session.execute(select(func.count(Application.id)))
    assert count.scalar_one() == 1


@pytest.mark.asyncio
async def test_classification_executor_sets_gap_status(db_session, patch_db_context, sample_document):
    from app.models import Application, ApplicationStatusEnum
    from app.validation_engine.executors import DocumentAiClassificationExecutor
    from app.validation_engine.schemas import DocumentAiClassificationConfig
    from app.validation_engine.models import ValidationRun

    executor = DocumentAiClassificationExecutor()
    config = DocumentAiClassificationConfig(
        classify_with_kimi=False,
        required_document_types=["pdd"],
    ).model_dump()
    run = ValidationRun(id=uuid.uuid4())
    context = {"application_id": str(sample_document.application_id)}

    result = await executor.execute(config, context, run)

    gaps = result["gap_findings"]
    assert gaps["has_gaps"] is True
    assert gaps["missing_document_types"] == ["pdd"]
    assert gaps["remediation"][0]["document_type"] == "pdd"

    application = await db_session.get(Application, sample_document.application_id)
    assert application.status == ApplicationStatusEnum.gaps
    assert application.gap_findings["missing_document_types"] == ["pdd"]


@pytest.mark.asyncio
async def test_classification_executor_no_gaps_advances_to_pre_audit(db_session, patch_db_context, sample_document):
    from app.models import Application, ApplicationStatusEnum
    from app.validation_engine.executors import DocumentAiClassificationExecutor
    from app.validation_engine.schemas import DocumentAiClassificationConfig
    from app.validation_engine.models import ValidationRun

    executor = DocumentAiClassificationExecutor()
    config = DocumentAiClassificationConfig(
        classify_with_kimi=False,
        required_document_types=[],
    ).model_dump()
    run = ValidationRun(id=uuid.uuid4())
    context = {"application_id": str(sample_document.application_id)}

    result = await executor.execute(config, context, run)

    assert result["gap_findings"]["has_gaps"] is False
    application = await db_session.get(Application, sample_document.application_id)
    assert application.status == ApplicationStatusEnum.pre_audit
