"""Default AI application pipeline workflow template."""

import hashlib
import json
import uuid
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.validation_engine.models import ValidationWorkflow
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_PIPELINE_NAME = "ai_application_pipeline"
DEFAULT_PIPELINE_VERSION = "1.0.0"


def build_ai_application_pipeline_graph() -> Dict[str, Any]:
    """Build the default 3-step AI application pipeline graph.

    intake -> collect_documents -> classify_documents -> end
    """
    return {
        "version": "1.0",
        "description": "AI-driven carbon credit application intake, document collection, and classification pipeline.",
        "entry_step": "intake",
        "steps": [
            {
                "id": "intake",
                "name": "Application Intake",
                "type": "application_intake",
                "description": "Create the Application record from applicant-submitted project basics.",
                "config": {
                    "applicant_email": "${input.applicant_email}",
                    "project_title": "${input.project_title}",
                    "organization_name": "${input.organization_name}",
                    "country": "${input.country}",
                    "sector": "${input.sector}",
                    "proposed_methodology": "${input.proposed_methodology}",
                },
                "next_on_success": ["collect_documents"],
            },
            {
                "id": "collect_documents",
                "name": "Document Collection",
                "type": "document_collection",
                "description": "Record discovered document slots and await applicant uploads.",
                "config": {
                    "sources": [{"type": "upload"}],
                    "required_document_types": ["pdd"],
                },
                "next_on_success": ["classify_documents"],
            },
            {
                "id": "classify_documents",
                "name": "Document AI Classification",
                "type": "document_ai_classification",
                "description": "Classify uploaded documents and extract entities with Kimi AI.",
                "config": {
                    "classify_with_kimi": True,
                    "extract_entities": True,
                    "required_document_types": ["pdd"],
                },
                "next_on_success": ["end"],
            },
        ],
    }


async def ensure_default_application_pipeline(db: AsyncSession) -> ValidationWorkflow:
    """Idempotently create the default AI application pipeline workflow template."""
    result = await db.execute(
        select(ValidationWorkflow).where(
            ValidationWorkflow.name == DEFAULT_PIPELINE_NAME,
            ValidationWorkflow.version == DEFAULT_PIPELINE_VERSION,
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow:
        return workflow

    graph = build_ai_application_pipeline_graph()
    graph_hash = hashlib.sha256(
        json.dumps(graph, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()

    workflow = ValidationWorkflow(
        id=uuid.uuid4(),
        name=DEFAULT_PIPELINE_NAME,
        version=DEFAULT_PIPELINE_VERSION,
        description=graph["description"],
        workflow_graph=graph,
        graph_hash=graph_hash,
        active=True,
        human_gates_required=False,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    logger.info("default_application_pipeline_created", workflow_id=str(workflow.id))
    return workflow
