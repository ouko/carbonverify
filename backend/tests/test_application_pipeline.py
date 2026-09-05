"""Tests for the default AI application pipeline workflow template."""

import pytest

from app.services.application_pipeline import (
    DEFAULT_PIPELINE_NAME,
    build_ai_application_pipeline_graph,
    ensure_default_application_pipeline,
)
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
