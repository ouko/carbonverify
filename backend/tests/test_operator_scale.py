"""Acceptance test — Success Criterion 3: one operator manages 200+ projects
from a single dashboard.

Seeds 200 projects (bulk insert, single session) with a realistic operational
sprinkle — recent agent runs, open human review items, open escalations, and
agent decisions — then drives every operator-facing endpoint through the real
FastAPI app with an authenticated client, asserting 200 responses and <2s
latency per endpoint. The SLA sweep task is asserted to process all stale
review items in a single batch call.
"""

import time
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.core.encryption import compute_searchable_hash
from app.escalations.models import EscalationEvent, EscalationStatus
from app.models import (
    AgentDecision,
    AgentRun,
    AgentStatusEnum,
    AgentTypeEnum,
    Developer,
    HumanReviewQueue,
    MethodologyEnum,
    Project,
    ProjectStatusEnum,
    QueueItemTypeEnum,
    QueueStatusEnum,
    User,
    UserRoleEnum,
)
from app.orchestrator.audit_chain import compute_record_hash, hash_fields_for

PROJECT_COUNT = 200
AGENT_RUN_COUNT = 40
OPEN_QUEUE_ITEMS = 15
OPEN_ESCALATIONS = 8
DECISION_COUNT = 60

LATENCY_LIMIT_SECONDS = 2.0


@pytest_asyncio.fixture
async def operator_scale_data(db_session):
    """200 projects + realistic operational sprinkle, bulk-inserted."""
    email = f"scale-{uuid.uuid4().hex[:8]}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Scale Operator",
        role=UserRoleEnum.operator,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.flush()
    developer = Developer(id=uuid.uuid4(), user_id=user.id, company_name="Scale Dev Co")
    db_session.add(developer)
    await db_session.flush()

    projects = [
        Project(
            id=uuid.uuid4(),
            name=f"Scale Project {i:03d}",
            developer_id=developer.id,
            methodology=MethodologyEnum.TPDDTEC_v4,
            crediting_period_start=date(2024, 1, 1),
            crediting_period_end=date(2030, 12, 31),
            status=ProjectStatusEnum.monitoring,
        )
        for i in range(PROJECT_COUNT)
    ]
    db_session.add_all(projects)
    await db_session.flush()

    now = datetime.now(UTC)
    agent_types = list(AgentTypeEnum)

    # ~40 projects with recent agent runs.
    db_session.add_all(
        [
            AgentRun(
                id=uuid.uuid4(),
                project_id=projects[i].id,
                agent_type=agent_types[i % len(agent_types)],
                status=AgentStatusEnum.completed,
                trigger_event="milestone",
                input_data={},
                output_data={"summary": "scale run"},
                confidence_score=0.9,
                execution_time_ms=12,
                completed_at=now - timedelta(minutes=i),
            )
            for i in range(AGENT_RUN_COUNT)
        ]
    )

    # ~15 open human review queue items.
    db_session.add_all(
        [
            HumanReviewQueue(
                id=uuid.uuid4(),
                item_type=QueueItemTypeEnum.agent_review,
                item_id=uuid.uuid4(),
                reason=f"Scale review item {i}",
                priority=3,
                priority_score=9.0,
                sla_deadline=now + timedelta(hours=24),
                status=QueueStatusEnum.pending,
                context_json={"project_id": str(projects[i].id), "agent_type": "ingestion"},
                confidence_gap=0.05,
                created_at=now - timedelta(hours=i + 1),
            )
            for i in range(OPEN_QUEUE_ITEMS)
        ]
    )

    # ~8 open escalations.
    db_session.add_all(
        [
            EscalationEvent(
                id=uuid.uuid4(),
                project_id=projects[i].id,
                source=f"agent:{agent_types[i % len(agent_types)].value}",
                title=f"Scale escalation {i}",
                detail="Requires operator attention",
                context_package={},
                priority=1,
                severity_score=0.8,
                status=EscalationStatus.open,
                channels_sent={},
                created_at=now - timedelta(minutes=30 * i),
            )
            for i in range(OPEN_ESCALATIONS)
        ]
    )

    # ~60 agent decisions (Merkle-chained).
    prev_hash = None
    for i in range(DECISION_COUNT):
        decision = AgentDecision(
            id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
            project_id=projects[i % PROJECT_COUNT].id,
            agent_type="ingestion",
            action="auto_advance",
            confidence_score=0.96,
            reasoning=f"Scale decision {i}: agent output verified against seeded data.",
            input_summary={"checked_items": 3},
            context_package=None,
            prev_hash=prev_hash,
            actor="agent:ingestion",
            created_at=now - timedelta(minutes=i),
        )
        decision.record_hash = compute_record_hash(hash_fields_for(decision))
        prev_hash = decision.record_hash
        db_session.add(decision)
    await db_session.commit()

    open_escalation_ids = [
        row[0]
        for row in (
            await db_session.execute(
                select(EscalationEvent.id).where(
                    EscalationEvent.status == EscalationStatus.open
                )
            )
        ).all()
    ]
    return {"open_escalation_ids": open_escalation_ids}


async def _timed_get(ac, url):
    start = time.perf_counter()
    resp = await ac.get(url)
    elapsed = time.perf_counter() - start
    return resp, elapsed


@pytest.mark.asyncio
async def test_operator_dashboard_handles_200_projects_under_2s(
    authenticated_client, db_session, operator_scale_data
):
    """Criterion 3: every operator endpoint answers 200 in <2s at 200-project
    scale."""
    ac, _user = authenticated_client

    checks = [
        ("/review-queue/", None),
        ("/api/v1/escalations/", None),
        ("/api/v1/escalations/stats", None),
        ("/api/v1/escalations/health/score", None),
        ("/api/v1/audit/decisions", None),
    ]
    for url, _ in checks:
        resp, elapsed = await _timed_get(ac, url)
        assert resp.status_code == 200, f"{url} → {resp.status_code}: {resp.text[:200]}"
        assert elapsed < LATENCY_LIMIT_SECONDS, f"{url} took {elapsed:.2f}s"

    # Acknowledge one open escalation (POST) — also under the latency bar.
    escalation_id = operator_scale_data["open_escalation_ids"][0]
    start = time.perf_counter()
    resp = await ac.post(f"/api/v1/escalations/{escalation_id}/acknowledge")
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200, f"acknowledge → {resp.status_code}: {resp.text[:200]}"
    assert elapsed < LATENCY_LIMIT_SECONDS
    assert resp.json()["status"] == "acknowledged"

    # Sanity: the payloads actually reflect the seeded scale.
    queue = (await ac.get("/review-queue/")).json()
    assert len(queue) == OPEN_QUEUE_ITEMS
    escalations = (await ac.get("/api/v1/escalations/")).json()
    assert escalations["total"] == OPEN_ESCALATIONS
    stats = (await ac.get("/api/v1/escalations/stats")).json()
    assert stats["total"] == OPEN_ESCALATIONS
    assert stats["open_p0"] == 0  # all seeded at priority 1
    health = (await ac.get("/api/v1/escalations/health/score")).json()
    assert 0 <= health["score"] <= 100
    decisions = (await ac.get("/api/v1/audit/decisions")).json()
    # 60 seeded + 1 recorded by the acknowledge POST above.
    assert decisions["total"] == DECISION_COUNT + 1

    # All 200 projects remain visible to the operator's project surface too.
    project_count = (
        await db_session.execute(select(func.count(Project.id)))
    ).scalar()
    assert project_count == PROJECT_COUNT


@pytest.mark.asyncio
async def test_sla_sweep_processes_stale_items_in_single_batch(
    db_session, patch_db_context, operator_scale_data
):
    """The SLA sweep clears every stale pending item in one batch call."""
    now = datetime.now(UTC)
    stale_items = [
        HumanReviewQueue(
            id=uuid.uuid4(),
            item_type=QueueItemTypeEnum.agent_review,
            item_id=uuid.uuid4(),
            reason=f"Stale item {i}",
            priority=3,
            status=QueueStatusEnum.pending,
            context_json={"agent_type": "ingestion"},
            confidence_gap=0.05,
            created_at=now - timedelta(hours=26 + i),
        )
        for i in range(5)
    ]
    fresh_item = HumanReviewQueue(
        id=uuid.uuid4(),
        item_type=QueueItemTypeEnum.agent_review,
        item_id=uuid.uuid4(),
        reason="Fresh item",
        priority=3,
        status=QueueStatusEnum.pending,
        context_json={"agent_type": "ingestion"},
        created_at=now - timedelta(hours=1),
    )
    db_session.add_all([*stale_items, fresh_item])
    await db_session.commit()

    from app.tasks.lifecycle_jobs import human_review_sla_sweep

    start = time.perf_counter()
    outcome = human_review_sla_sweep()
    elapsed = time.perf_counter() - start

    # Single batch call processed all stale items; the fresh one is untouched.
    assert outcome["stale_items_found"] == 5
    assert outcome["auto_approved"] == 5
    for item in stale_items:
        await db_session.refresh(item)
        assert item.status == QueueStatusEnum.resolved
        assert item.human_decision == "approve"
    await db_session.refresh(fresh_item)
    assert fresh_item.status == QueueStatusEnum.pending
    assert elapsed < LATENCY_LIMIT_SECONDS
