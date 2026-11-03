"""Pre-defined synthetic E2E journey templates for continuous validation.

Three workflow graphs exercise the core product paths end-to-end through the
existing Workflow Validation Engine:

- ``synthetic_developer_journey`` — a project developer registers, creates a
  project, uploads data fixtures, runs a calculation, generates a report draft,
  and the project advances onboarding → data_collection → calculation → review.
- ``synthetic_enumerator_journey`` — a field enumerator's offline batch is
  synced with conflict resolution; no data is lost and provenance is recorded.
- ``synthetic_calc_anomaly_recovery`` — a calculation anomaly is injected and
  auto-remediated by the shared remediation engine (first attempt fails,
  second succeeds); the after-state hash is recorded and no escalation fires.

The graphs use only ``service_call`` (hermetic, in-process), ``database_query``
(read-only) and ``decision_gate`` step types — never raw HTTP — so they run
anywhere the engine runs. Runs are tagged with a synthetic actor marker via
``input_data["actor_marker"]``.
"""

import hashlib
import json
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.validation_engine.models import ValidationWorkflow
from app.validation_engine.schemas import WorkflowGraph

JOURNEY_VERSION = "1.0.0"

SERVICE_NAME = "validation_journeys"


def _service_step(
    step_id: str,
    name: str,
    method_name: str,
    args: List[Any],
    next_on_success: List[str],
    next_on_failure: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "id": step_id,
        "name": name,
        "type": "service_call",
        "config": {
            "service_name": SERVICE_NAME,
            "method_name": method_name,
            "args": args,
        },
        "next_on_success": next_on_success,
        "next_on_failure": next_on_failure or ["fail"],
    }


def _developer_journey() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "description": (
            "Synthetic project developer: register → create project → upload "
            "fixture data → run calculation → generate report draft → reach review."
        ),
        "entry_step": "register_developer",
        "steps": [
            _service_step(
                "register_developer",
                "Register synthetic developer account",
                "register_developer",
                ["${input.actor_marker}"],
                ["create_project"],
            ),
            _service_step(
                "create_project",
                "Create project in onboarding state",
                "create_project",
                ["${outputs.register_developer.result.developer_id}", "${input.project_name}"],
                ["upload_fixture_data"],
            ),
            _service_step(
                "upload_fixture_data",
                "Upload small in-DB data fixture",
                "create_fixture_data",
                ["${outputs.create_project.result.project_id}", "${input.actor_marker}"],
                ["run_calculation"],
            ),
            _service_step(
                "run_calculation",
                "Run calculation and advance project lifecycle",
                "run_calculation",
                ["${outputs.create_project.result.project_id}"],
                ["generate_report_draft"],
            ),
            _service_step(
                "generate_report_draft",
                "Generate report draft",
                "generate_report_draft",
                [
                    "${outputs.create_project.result.project_id}",
                    "${outputs.run_calculation.result.calculation_id}",
                ],
                ["verify_project_record"],
            ),
            {
                "id": "verify_project_record",
                "name": "Verify project persisted via read-only query",
                "type": "database_query",
                "config": {
                    "query": "SELECT name, status FROM projects WHERE name = :name",
                    "params": {"name": "${input.project_name}"},
                    "snapshot_result": True,
                },
                "next_on_success": ["assert_lifecycle_gate"],
                "next_on_failure": ["fail"],
            },
            {
                "id": "assert_lifecycle_gate",
                "name": "Check onboarding → data_collection → calculation → review",
                "type": "decision_gate",
                "config": {
                    "condition_expression": (
                        "'onboarding' in ${outputs.run_calculation.result.transition_log} "
                        "and 'data_collection' in ${outputs.run_calculation.result.transition_log} "
                        "and 'calculation' in ${outputs.run_calculation.result.transition_log} "
                        "and 'review' in ${outputs.run_calculation.result.transition_log}"
                    ),
                },
                "next_on_success": ["assert_lifecycle"],
                "next_on_failure": ["assert_lifecycle"],
            },
            _service_step(
                "assert_lifecycle",
                "Assert project reached review through the full lifecycle",
                "assert_true",
                [
                    "${outputs.assert_lifecycle_gate.result}",
                    "developer journey: project did not reach review via the full lifecycle",
                ],
                ["end"],
            ),
        ],
        "variables": {},
    }


def _enumerator_journey() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "description": (
            "Synthetic field enumerator: offline survey batch is synced with "
            "conflict resolution — row count preserved, provenance recorded."
        ),
        "entry_step": "create_offline_batch",
        "steps": [
            _service_step(
                "create_offline_batch",
                "Create enumerator and offline survey batch",
                "create_offline_batch",
                ["${input.actor_marker}", "${input.project_name}"],
                ["sync_offline_batch"],
            ),
            _service_step(
                "sync_offline_batch",
                "Sync offline batch and resolve conflicts",
                "sync_offline_batch",
                ["${outputs.create_offline_batch.result.project_id}", "${input.actor_marker}"],
                ["verify_response_count"],
            ),
            {
                "id": "verify_response_count",
                "name": "Snapshot synced survey responses",
                "type": "database_query",
                "config": {
                    "query": (
                        "SELECT COUNT(*) AS synced_count FROM survey_responses "
                        "WHERE submitted_via = 'whatsapp'"
                    ),
                    "params": {},
                    "snapshot_result": True,
                },
                "next_on_success": ["assert_no_data_loss_gate"],
                "next_on_failure": ["fail"],
            },
            {
                "id": "assert_no_data_loss_gate",
                "name": "Check no data loss and provenance recorded",
                "type": "decision_gate",
                "config": {
                    "condition_expression": (
                        "${outputs.sync_offline_batch.result.data_loss} == False "
                        "and ${outputs.sync_offline_batch.result.conflicts_resolved} >= 1 "
                        "and ${outputs.sync_offline_batch.result.provenance_recorded} == True"
                    ),
                },
                "next_on_success": ["assert_no_data_loss"],
                "next_on_failure": ["assert_no_data_loss"],
            },
            _service_step(
                "assert_no_data_loss",
                "Assert offline sync lost no data and recorded provenance",
                "assert_true",
                [
                    "${outputs.assert_no_data_loss_gate.result}",
                    "enumerator journey: offline sync lost data or missed provenance",
                ],
                ["end"],
            ),
        ],
        "variables": {},
    }


def _anomaly_recovery_journey() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "description": (
            "Synthetic calculation anomaly: injected failure is auto-remediated "
            "(first attempt fails, second succeeds), after-state hash recorded, "
            "no human escalation created."
        ),
        "entry_step": "inject_and_remediate_anomaly",
        "steps": [
            _service_step(
                "inject_and_remediate_anomaly",
                "Inject anomaly and run auto-remediation",
                "inject_and_remediate_anomaly",
                ["${input.actor_marker}", "${input.target_name}"],
                ["verify_no_escalation"],
            ),
            _service_step(
                "verify_no_escalation",
                "Verify no human escalation was created",
                "count_escalations_for_target",
                ["${outputs.inject_and_remediate_anomaly.result.target_id}"],
                ["assert_resolved_gate"],
            ),
            {
                "id": "assert_resolved_gate",
                "name": "Check resolved with after-state hash and zero escalations",
                "type": "decision_gate",
                "config": {
                    "condition_expression": (
                        "${outputs.inject_and_remediate_anomaly.result.status} == 'resolved' "
                        "and len(${outputs.inject_and_remediate_anomaly.result.after_state_hash}) == 64 "
                        "and ${outputs.verify_no_escalation.result.escalations} == 0"
                    ),
                },
                "next_on_success": ["assert_resolved"],
                "next_on_failure": ["assert_resolved"],
            },
            _service_step(
                "assert_resolved",
                "Assert anomaly auto-remediation resolved cleanly",
                "assert_true",
                [
                    "${outputs.assert_resolved_gate.result}",
                    "anomaly journey: anomaly was not resolved cleanly (hash/escalation check failed)",
                ],
                ["end"],
            ),
        ],
        "variables": {},
    }


_JOURNEY_BUILDERS = {
    "synthetic_developer_journey": _developer_journey,
    "synthetic_enumerator_journey": _enumerator_journey,
    "synthetic_calc_anomaly_recovery": _anomaly_recovery_journey,
}


def get_journey_templates() -> Dict[str, Dict[str, Any]]:
    """Return the three journey graph dicts, each validated by WorkflowGraph."""
    templates = {name: builder() for name, builder in _JOURNEY_BUILDERS.items()}
    for name, graph in templates.items():
        WorkflowGraph.model_validate(graph)
    return templates


def get_journey_names() -> List[str]:
    return list(_JOURNEY_BUILDERS.keys())


def compute_graph_hash(graph: Dict[str, Any]) -> str:
    canonical = json.dumps(graph, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def ensure_journey_workflows(
    db: AsyncSession,
    templates: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, ValidationWorkflow]:
    """Upsert one ValidationWorkflow row per journey template (by name+version).

    Returns a mapping of journey name to workflow. Existing rows are returned
    untouched so operator edits are never clobbered.
    """
    templates = templates or get_journey_templates()
    workflows: Dict[str, ValidationWorkflow] = {}

    existing_result = await db.execute(
        select(ValidationWorkflow).where(
            ValidationWorkflow.name.in_(list(templates.keys())),
            ValidationWorkflow.version == JOURNEY_VERSION,
        )
    )
    existing = {wf.name: wf for wf in existing_result.scalars().all()}

    for name, graph in templates.items():
        workflow = existing.get(name)
        if workflow is None:
            workflow = ValidationWorkflow(
                name=name,
                version=JOURNEY_VERSION,
                description=graph.get("description"),
                workflow_graph=graph,
                graph_hash=compute_graph_hash(graph),
                active=True,
            )
            db.add(workflow)
            existing[name] = workflow
        workflows[name] = workflow

    await db.commit()
    for workflow in workflows.values():
        await db.refresh(workflow)
    return workflows
