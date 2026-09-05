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
    assert trigger_response.json()["status"] == "intake"
