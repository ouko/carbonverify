"""Tests for the default AI application pipeline workflow template."""

import pytest

from app.services.application_pipeline import (
    DEFAULT_PIPELINE_NAME,
    build_ai_application_pipeline_graph,
    ensure_default_application_pipeline,
)
from app.validation_engine.executors import StepExecutorRegistry
from app.validation_engine.models import WorkflowStepType
from app.validation_engine.schemas import WorkflowGraph


@pytest.mark.asyncio
async def test_default_pipeline_exists(db_session):
    workflow = await ensure_default_application_pipeline(db_session)
    assert workflow.name == DEFAULT_PIPELINE_NAME
    assert workflow.workflow_graph["steps"][0]["type"] == "application_intake"


@pytest.mark.asyncio
async def test_default_pipeline_graph_is_valid(db_session):
    graph = build_ai_application_pipeline_graph()
    validated = WorkflowGraph.model_validate(graph)
    assert validated.entry_step == "intake"
    assert len(validated.steps) == 3
    assert validated.steps[0].type == "application_intake"


@pytest.mark.asyncio
async def test_default_pipeline_is_idempotent(db_session):
    first = await ensure_default_application_pipeline(db_session)
    second = await ensure_default_application_pipeline(db_session)
    assert first.id == second.id


@pytest.mark.asyncio
async def test_full_intake_to_classification_flow(client, authenticated_client, db_session):
    # 1. Submit intake via the public endpoint
    intake_response = await client.post("/applications", json={
        "applicant_email": "owner@example.com",
        "project_title": "Kenya Stoves",
        "country": "Kenya",
        "sector": "cookstoves",
    })
    assert intake_response.status_code == 201
    app_id = intake_response.json()["id"]

    # 2. Ensure pipeline template exists and is schema-valid
    workflow = await ensure_default_application_pipeline(db_session)
    assert workflow.name == DEFAULT_PIPELINE_NAME
    graph = WorkflowGraph.model_validate(workflow.workflow_graph)
    assert graph.steps[0].type == WorkflowStepType.application_intake

    # 3. Every pipeline step type has a registered executor
    registry = StepExecutorRegistry()
    for step in graph.steps:
        assert registry.get_executor(step.type) is not None

    # 4. Trigger pipeline (Phase 2 will actually run it end-to-end)
    auth_client, _ = authenticated_client
    trigger_response = await auth_client.post(f"/applications/{app_id}/trigger-pipeline")
    assert trigger_response.status_code == 200
    # Triggering marks the application as awaiting document processing
    assert trigger_response.json()["status"] == "documents_pending"


@pytest.mark.asyncio
async def test_full_pipeline_execution_via_orchestrator(db_session, patch_db_context, sample_application):
    """Execute the ai_application_pipeline end-to-end through the orchestrator."""
    from app.models import ApplicationStatusEnum
    from app.services.application_pipeline import ensure_default_application_pipeline
    from app.validation_engine.models import ValidationRun, WorkflowRunStatus
    from app.validation_engine.orchestrator import ValidationOrchestrator

    workflow = await ensure_default_application_pipeline(db_session)
    orchestrator = ValidationOrchestrator(db_session)
    run = await orchestrator.create_run(
        workflow_id=str(workflow.id),
        trigger_event="application_pipeline",
        input_data={
            "application_id": str(sample_application.id),
            "applicant_email": "owner@example.com",
            "project_title": "Sample Project",
        },
    )
    # The trigger endpoint links the run to the application before executing
    sample_application.validation_run_id = run.id
    await db_session.commit()

    result: ValidationRun = await orchestrator.execute_workflow(str(run.id))

    assert result.status == WorkflowRunStatus.completed

    # Intake step must not have duplicated the application; collection +
    # classification must have run and advanced the application status
    await db_session.refresh(sample_application)
    assert sample_application.status in (
        ApplicationStatusEnum.gaps,
        ApplicationStatusEnum.pre_audit,
    )
