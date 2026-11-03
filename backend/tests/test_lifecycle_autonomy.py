"""Tests for autonomous lifecycle orchestration (advance_project, SLA sweep, scan)."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

import app.orchestrator.orchestrator as orchestrator_module
from app.agents import AgentResult
from app.core.encryption import compute_searchable_hash
from app.models import (
    AgentDecision,
    HumanReviewQueue,
    MethodologyEnum,
    Project,
    ProjectStatusEnum,
    QueueItemTypeEnum,
    QueueStatusEnum,
    User,
    UserRoleEnum,
)
from app.orchestrator.orchestrator import KimiClawOrchestrator

ALL_LIFECYCLE_AGENT_TYPES = [
    "ingestion",
    "client_success",
    "validation",
    "calculation",
    "quality_control",
    "reporting",
    "vvb_liaison",
]


def _make_fake_agent(score: float, status: str = "completed"):
    """Build a fake agent class that always returns the given confidence."""

    class FakeAgent:
        def __init__(self, project_id, db_session=None):
            self.project_id = project_id
            self.db = db_session

        async def execute(self, trigger_event, context):
            return AgentResult(
                status=status,
                confidence_score=score,
                output_data={"summary": "fake run", "checked_items": 3},
                execution_time_ms=1,
            )

    return FakeAgent


@pytest_asyncio.fixture
async def seeded_project(db_session):
    email = f"dev-{uuid.uuid4().hex[:8]}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Lifecycle Dev",
        role=UserRoleEnum.developer,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.commit()

    from app.models import Developer

    developer = Developer(id=uuid.uuid4(), user_id=user.id, company_name="Acme MRV")
    db_session.add(developer)
    await db_session.commit()

    project = Project(
        id=uuid.uuid4(),
        name="Lifecycle Test Project",
        developer_id=developer.id,
        methodology=MethodologyEnum.TPDDTEC_v4,
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        status=ProjectStatusEnum.onboarding,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
def patch_agents(monkeypatch):
    """Patch the orchestrator's agent registry with fake agents.

    Usage: patch_agents(0.96) or patch_agents({"ingestion": 0.90, ...}).
    Returns the applied score mapping.
    """

    def _patch(scores):
        if isinstance(scores, (int, float)):
            scores = {agent_type: float(scores) for agent_type in ALL_LIFECYCLE_AGENT_TYPES}
        for agent_type, score in scores.items():
            monkeypatch.setitem(
                orchestrator_module.AGENT_REGISTRY, agent_type, _make_fake_agent(score)
            )
        return scores

    return _patch


async def _project_status(db_session, project_id):
    result = await db_session.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one().status


async def _decisions(db_session, action=None):
    query = select(AgentDecision)
    if action:
        query = query.where(AgentDecision.action == action)
    result = await db_session.execute(query)
    return result.scalars().all()


@pytest.mark.asyncio
async def test_advance_project_auto_transitions(db_session, seeded_project, patch_agents):
    patch_agents(0.96)
    orchestrator = KimiClawOrchestrator(db_session)

    result = await orchestrator.advance_project(seeded_project.id, max_steps=5)

    # Walk the nested result chain. Five transitions land on "verified",
    # which is a steady state, so advancement stops there.
    states = [result["state"]]
    node = result
    while node.get("advanced"):
        states.append(node["to_state"])
        node = node["next"]
    assert states == [
        "onboarding",
        "data_collection",
        "calculation",
        "review",
        "submitted",
        "verified",
    ]

    assert await _project_status(db_session, seeded_project.id) == ProjectStatusEnum.verified

    # Each agent run recorded an auto_advance decision.
    auto_decisions = await _decisions(db_session, action="auto_advance")
    assert len(auto_decisions) == 8  # 2+2+2+1+1 agent runs across the five transitions
    assert all(d.confidence_score >= 0.95 for d in auto_decisions)


@pytest.mark.asyncio
async def test_advance_stops_and_queues_review_at_0_90(db_session, seeded_project, patch_agents):
    patch_agents(0.90)
    orchestrator = KimiClawOrchestrator(db_session)

    result = await orchestrator.advance_project(seeded_project.id, max_steps=5)

    assert result["advanced"] is False
    assert result["reason"] == "insufficient_confidence"
    assert await _project_status(db_session, seeded_project.id) == ProjectStatusEnum.onboarding

    # A priority-3 review item was queued and linked to a queued_for_review decision.
    items = (await db_session.execute(select(HumanReviewQueue))).scalars().all()
    assert len(items) == 2  # both onboarding agents queued review
    assert all(i.priority == 3 for i in items)
    assert all(i.decision_id is not None for i in items)

    queued = await _decisions(db_session, action="queued_for_review")
    assert len(queued) == 2
    assert all(d.review_queue_item_id is not None for d in queued)


@pytest.mark.asyncio
async def test_advance_escalates_below_0_85(db_session, seeded_project, patch_agents):
    patch_agents(0.80)
    orchestrator = KimiClawOrchestrator(db_session)

    result = await orchestrator.advance_project(seeded_project.id, max_steps=5)

    assert result["advanced"] is False
    assert await _project_status(db_session, seeded_project.id) == ProjectStatusEnum.onboarding

    items = (await db_session.execute(select(HumanReviewQueue))).scalars().all()
    assert len(items) == 2
    assert all(i.priority == 5 for i in items)

    escalated = await _decisions(db_session, action="escalated")
    assert len(escalated) == 2


@pytest.mark.asyncio
async def test_advance_respects_max_steps(db_session, seeded_project, patch_agents):
    patch_agents(0.96)
    orchestrator = KimiClawOrchestrator(db_session)

    result = await orchestrator.advance_project(seeded_project.id, max_steps=1)

    assert result["advanced"] is True
    assert result["to_state"] == "data_collection"
    assert result["next"]["advanced"] is False
    assert result["next"]["reason"] == "max_steps"
    assert await _project_status(db_session, seeded_project.id) == ProjectStatusEnum.data_collection


@pytest.mark.asyncio
async def test_advance_loop_guard(db_session, seeded_project, patch_agents, monkeypatch):
    patch_agents(0.96)
    # Cyclic state machine: onboarding ⇄ data_collection, with a trigger that
    # always resolves, so only the visited-state guard can stop the recursion.
    monkeypatch.setattr(
        orchestrator_module,
        "STATE_TRANSITIONS",
        {
            ProjectStatusEnum.onboarding: {
                "data_collection": [orchestrator_module.AgentTypeEnum.ingestion]
            },
            ProjectStatusEnum.data_collection: {
                "onboarding": [orchestrator_module.AgentTypeEnum.ingestion]
            },
        },
    )
    monkeypatch.setattr(orchestrator_module, "trigger_for_next_state", lambda _state: "data_complete")
    orchestrator = KimiClawOrchestrator(db_session)

    result = await orchestrator.advance_project(seeded_project.id, max_steps=10)

    assert result["advanced"] is True
    assert result["next"]["advanced"] is True
    assert result["next"]["next"]["advanced"] is False
    assert result["next"]["next"]["reason"] == "loop_guard"


@pytest.mark.asyncio
async def test_advance_ignores_steady_states(db_session, seeded_project, patch_agents):
    patch_agents(0.96)
    seeded_project.status = ProjectStatusEnum.monitoring
    await db_session.commit()

    orchestrator = KimiClawOrchestrator(db_session)
    result = await orchestrator.advance_project(seeded_project.id, max_steps=5)

    assert result["advanced"] is False
    assert result["reason"] == "steady_state"


@pytest.mark.asyncio
async def test_resolve_human_review_records_decision(db_session, seeded_project, patch_agents):
    patch_agents(0.90)
    orchestrator = KimiClawOrchestrator(db_session)
    await orchestrator.advance_project(seeded_project.id, max_steps=1)

    item = (await db_session.execute(select(HumanReviewQueue))).scalars().first()
    resolution = await orchestrator.resolve_human_review(
        queue_item_id=item.id,
        decision="approve",
        resolution_notes="Looks good after manual inspection.",
        user_id=uuid.uuid4(),
        actor="reviewer@carbonverify.io",
    )

    assert resolution["status"] == "resolved"

    human = await _decisions(db_session, action="human_approved")
    assert len(human) == 1
    assert human[0].actor == "reviewer@carbonverify.io"
    assert human[0].review_queue_item_id == item.id
    assert "manual inspection" in human[0].reasoning

    # The full chain — routing + resolution — still verifies.
    from app.orchestrator.audit_chain import verify_chain

    assert (await verify_chain(db_session))["valid"] is True


@pytest.mark.asyncio
async def test_sla_sweep_auto_approves_stale_item(db_session, seeded_project, patch_db_context):
    stale_item = HumanReviewQueue(
        item_type=QueueItemTypeEnum.agent_review,
        item_id=uuid.uuid4(),
        reason="Agent confidence 0.90 below auto-advance threshold (0.95)",
        priority=3,
        status=QueueStatusEnum.pending,
        context_json={
            "project_id": str(seeded_project.id),
            "agent_type": "ingestion",
            "agent_run_id": str(uuid.uuid4()),
        },
        confidence_gap=0.05,
        created_at=datetime.now(UTC) - timedelta(hours=25),
    )
    fresh_item = HumanReviewQueue(
        item_type=QueueItemTypeEnum.agent_review,
        item_id=uuid.uuid4(),
        reason="Recently queued",
        priority=3,
        status=QueueStatusEnum.pending,
        context_json={"project_id": str(seeded_project.id), "agent_type": "ingestion"},
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    urgent_item = HumanReviewQueue(
        item_type=QueueItemTypeEnum.agent_review,
        item_id=uuid.uuid4(),
        reason="Critical escalation",
        priority=5,
        status=QueueStatusEnum.pending,
        context_json={"project_id": str(seeded_project.id), "agent_type": "ingestion"},
        created_at=datetime.now(UTC) - timedelta(hours=48),
    )
    db_session.add_all([stale_item, fresh_item, urgent_item])
    await db_session.commit()

    from app.tasks.lifecycle_jobs import human_review_sla_sweep

    outcome = human_review_sla_sweep()

    assert outcome["stale_items_found"] == 1
    assert outcome["auto_approved"] == 1

    await db_session.refresh(stale_item)
    await db_session.refresh(fresh_item)
    await db_session.refresh(urgent_item)
    assert stale_item.status == QueueStatusEnum.resolved
    assert stale_item.human_decision == "approve"
    assert fresh_item.status == QueueStatusEnum.pending
    assert urgent_item.status == QueueStatusEnum.pending

    sla_decisions = await _decisions(db_session, action="sla_auto_approved")
    assert len(sla_decisions) == 1
    assert sla_decisions[0].actor == "system:sla_sweep"
    assert sla_decisions[0].review_queue_item_id == stale_item.id


@pytest.mark.asyncio
async def test_lifecycle_scan_enqueues_ready_projects(
    db_session, seeded_project, patch_db_context, monkeypatch
):
    # seeded_project is in onboarding with no agent runs → never ran → enqueue.
    steady_project = Project(
        id=uuid.uuid4(),
        name="Steady Project",
        developer_id=seeded_project.developer_id,
        methodology=MethodologyEnum.TPDDTEC_v4,
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        status=ProjectStatusEnum.monitoring,
    )
    db_session.add(steady_project)
    await db_session.commit()

    enqueued_ids = []

    def fake_delay(project_id):
        enqueued_ids.append(project_id)

    monkeypatch.setattr(
        "app.tasks.lifecycle_jobs.advance_project_task.delay", fake_delay
    )

    from app.tasks.lifecycle_jobs import lifecycle_scan

    outcome = lifecycle_scan()

    # Only the onboarding project is in a drive state; monitoring is excluded.
    assert outcome["projects_checked"] == 1
    assert outcome["enqueued"] == 1
    assert outcome["skipped"] == 0
    assert enqueued_ids == [str(seeded_project.id)]


@pytest.mark.asyncio
async def test_advance_project_task_runs_via_db_context(
    db_session, seeded_project, patch_agents, patch_db_context
):
    patch_agents(0.96)

    from app.tasks.lifecycle_jobs import advance_project_task

    result = advance_project_task(str(seeded_project.id))

    assert result["advanced"] is True
    # Default max_steps=3: onboarding → data_collection → calculation → review.
    assert await _project_status(db_session, seeded_project.id) == ProjectStatusEnum.review
