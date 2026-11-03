"""Tests for the Phase 3 human escalation & notification service."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

import app.orchestrator.orchestrator as orchestrator_module
from app.core.encryption import compute_searchable_hash
from app.escalations.channels import ChannelResult, InAppChannel
from app.escalations.models import EscalationEvent, EscalationStatus
from app.escalations.service import (
    PRIORITY_P0,
    PRIORITY_P1,
    PRIORITY_P2,
    EscalationService,
    derive_priority,
)
from app.models import (
    AgentDecision,
    Developer,
    MethodologyEnum,
    Project,
    ProjectStatusEnum,
    User,
    UserRoleEnum,
)
from app.orchestrator.orchestrator import KimiClawOrchestrator

ALL_AGENT_TYPES = [
    "ingestion",
    "validation",
    "calculation",
    "quality_control",
    "reporting",
    "vvb_liaison",
    "client_success",
]


def _make_fake_agent(score: float):
    from app.agents.base import AgentResult

    class FakeAgent:
        def __init__(self, project_id, db_session=None):
            self.project_id = project_id
            self.db = db_session

        async def execute(self, trigger_event, context):
            return AgentResult(
                status="completed",
                confidence_score=score,
                output_data={"summary": "fake run"},
                execution_time_ms=1,
            )

    return FakeAgent


@pytest.fixture
def patch_agents(monkeypatch):
    def _patch(score):
        for agent_type in ALL_AGENT_TYPES:
            monkeypatch.setitem(
                orchestrator_module.AGENT_REGISTRY, agent_type, _make_fake_agent(score)
            )

    return _patch


@pytest_asyncio.fixture
async def seeded_project(db_session):
    email = f"esc-{uuid.uuid4().hex[:8]}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Escalation Dev",
        role=UserRoleEnum.developer,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.commit()

    developer = Developer(
        id=uuid.uuid4(), user_id=user.id, company_name="Acme MRV"
    )
    db_session.add(developer)
    await db_session.commit()

    project = Project(
        id=uuid.uuid4(),
        name="Escalation Test Project",
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


class _FakeAdapter:
    def __init__(self, name, success=True, configured=True):
        self.name = name
        self.success = success
        self.configured = configured
        self.calls = []

    async def send(self, event):
        self.calls.append(event.id)
        return ChannelResult(
            channel=self.name,
            success=self.success,
            configured=self.configured,
            detail="" if self.success else "simulated failure",
        )


def _fake_adapters(**overrides):
    adapters = {
        "whatsapp": _FakeAdapter("whatsapp"),
        "sms": _FakeAdapter("sms"),
        "email": _FakeAdapter("email"),
        "in_app": _FakeAdapter("in_app"),
    }
    adapters.update(overrides)
    return adapters


# ─── Priority derivation ─────────────────────────────────────────────────────

class TestPriorityDerivation:
    def test_severity_to_priority(self):
        assert derive_priority(0.95) == PRIORITY_P0
        assert derive_priority(0.9) == PRIORITY_P0
        assert derive_priority(0.85) == PRIORITY_P1
        assert derive_priority(0.7) == PRIORITY_P1
        assert derive_priority(0.69) == PRIORITY_P2
        assert derive_priority(0.1) == PRIORITY_P2

    @pytest.mark.asyncio
    async def test_raise_escalation_derives_priority(self, db_session):
        service = EscalationService(db_session)
        p0 = await service.raise_escalation("agent:test", "t", "d", severity_score=0.95)
        assert p0.priority == PRIORITY_P0
        p1 = await service.raise_escalation("agent:test", "t", "d", severity_score=0.75)
        assert p1.priority == PRIORITY_P1
        p2 = await service.raise_escalation("agent:test", "t", "d", severity_score=0.3)
        assert p2.priority == PRIORITY_P2

    @pytest.mark.asyncio
    async def test_raise_escalation_explicit_priority_wins(self, db_session):
        service = EscalationService(db_session)
        event = await service.raise_escalation(
            "system:remediation", "t", "d", priority=PRIORITY_P1, severity_score=0.95
        )
        assert event.priority == PRIORITY_P1
        assert event.severity_score == 0.95
        assert event.status == EscalationStatus.open

    @pytest.mark.asyncio
    async def test_raise_escalation_invalid_priority(self, db_session):
        service = EscalationService(db_session)
        with pytest.raises(ValueError):
            await service.raise_escalation("agent:test", "t", "d", priority=5)

    @pytest.mark.asyncio
    async def test_clamps_severity(self, db_session):
        service = EscalationService(db_session)
        high = await service.raise_escalation("agent:test", "t", "d", severity_score=1.7)
        assert high.severity_score == 1.0


# ─── Dispatch ────────────────────────────────────────────────────────────────

class TestDispatch:
    @pytest.mark.asyncio
    async def test_p0_dispatches_all_channels_and_records(self, db_session):
        adapters = _fake_adapters()
        service = EscalationService(db_session, adapters=adapters)
        event = await service.raise_escalation(
            "agent:validation", "Low confidence", "detail", priority=PRIORITY_P0
        )
        for adapter in adapters.values():
            assert event.id in adapter.calls
        assert set(event.channels_sent.keys()) == {"whatsapp", "sms", "email", "in_app"}
        for record in event.channels_sent.values():
            assert record["success"] is True
            assert record["configured"] is True
            assert record["sent_at"]

    @pytest.mark.asyncio
    async def test_channel_failure_never_raises(self, db_session):
        failing = _FakeAdapter("email", success=False)
        adapters = _fake_adapters(email=failing)
        service = EscalationService(db_session, adapters=adapters)
        event = await service.raise_escalation(
            "agent:validation", "t", "d", priority=PRIORITY_P0
        )
        assert event.channels_sent["email"]["success"] is False
        # Other channels still attempted after the failure.
        assert event.channels_sent["in_app"]["success"] is True

    @pytest.mark.asyncio
    async def test_adapter_exception_recorded_and_continues(self, db_session):
        class CrashingAdapter:
            name = "sms"

            async def send(self, event):
                raise RuntimeError("boom")

        adapters = _fake_adapters(sms=CrashingAdapter())
        service = EscalationService(db_session, adapters=adapters)
        event = await service.raise_escalation(
            "agent:validation", "t", "d", priority=PRIORITY_P0
        )
        assert event.channels_sent["sms"]["success"] is False
        assert "boom" in event.channels_sent["sms"]["detail"]
        assert event.channels_sent["email"]["success"] is True

    @pytest.mark.asyncio
    async def test_p2_dispatches_nothing(self, db_session):
        adapters = _fake_adapters()
        service = EscalationService(db_session, adapters=adapters)
        event = await service.raise_escalation(
            "agent:validation", "t", "d", priority=PRIORITY_P2
        )
        assert event.channels_sent == {}
        assert all(adapter.calls == [] for adapter in adapters.values())

    @pytest.mark.asyncio
    async def test_log_only_adapters_without_credentials(self, db_session):
        """With no credentials configured, real adapters report not_configured."""
        service = EscalationService(db_session)
        event = await service.raise_escalation(
            "agent:validation", "t", "d", priority=PRIORITY_P0
        )
        assert event.channels_sent["whatsapp"]["configured"] is False
        assert event.channels_sent["sms"]["configured"] is False
        assert event.channels_sent["email"]["configured"] is False

    @pytest.mark.asyncio
    async def test_in_app_channel_uses_frontend_event_shape(self, db_session, monkeypatch):
        published = []

        class StubPubSub:
            async def publish_event(self, event_type, payload):
                published.append((event_type, payload))

        monkeypatch.setattr("app.orchestrator.pubsub.agent_pubsub", StubPubSub())
        event = await service_create_event(db_session)
        result = await InAppChannel().send(event)
        assert result.success is True
        event_type, payload = published[0]
        assert event_type == "agent_escalation"
        assert payload["agent_type"] == event.source
        assert payload["escalation_id"] == str(event.id)
        assert payload["priority"] == event.priority


async def service_create_event(db_session):
    service = EscalationService(db_session)
    return await service.raise_escalation(
        "agent:validation", "t", "d", priority=PRIORITY_P2
    )


# ─── Acknowledge / resolve ───────────────────────────────────────────────────

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_acknowledge_transitions_and_audits(self, db_session):
        service = EscalationService(db_session)
        event = await service.raise_escalation("agent:test", "t", "d")
        user_id = uuid.uuid4()

        updated = await service.acknowledge(event.id, user_id)
        assert updated.status == EscalationStatus.acknowledged
        assert updated.acknowledged_by == user_id
        assert updated.acknowledged_at is not None

        decisions = (
            await db_session.execute(select(AgentDecision))
        ).scalars().all()
        ack_decisions = [d for d in decisions if d.action == "escalation_acknowledged"]
        assert len(ack_decisions) == 1
        assert ack_decisions[0].actor == f"human:{user_id}"

    @pytest.mark.asyncio
    async def test_resolve_transitions_and_audits(self, db_session):
        service = EscalationService(db_session)
        event = await service.raise_escalation("agent:test", "t", "d")
        user_id = uuid.uuid4()

        resolved = await service.resolve(event.id, user_id, "fixed upstream")
        assert resolved.status == EscalationStatus.resolved
        assert resolved.resolved_by == user_id
        assert resolved.resolved_at is not None
        assert resolved.resolution_notes == "fixed upstream"

        decisions = (
            await db_session.execute(select(AgentDecision))
        ).scalars().all()
        res_decisions = [d for d in decisions if d.action == "escalation_resolved"]
        assert len(res_decisions) == 1
        assert "fixed upstream" in res_decisions[0].reasoning

    @pytest.mark.asyncio
    async def test_resolve_after_acknowledge_keeps_ack(self, db_session):
        service = EscalationService(db_session)
        event = await service.raise_escalation("agent:test", "t", "d")
        acker, resolver = uuid.uuid4(), uuid.uuid4()

        await service.acknowledge(event.id, acker)
        resolved = await service.resolve(event.id, resolver, "done")
        assert resolved.acknowledged_by == acker
        assert resolved.resolved_by == resolver

    @pytest.mark.asyncio
    async def test_double_resolve_rejected(self, db_session):
        service = EscalationService(db_session)
        event = await service.raise_escalation("agent:test", "t", "d")
        await service.resolve(event.id, uuid.uuid4(), "once")
        with pytest.raises(ValueError):
            await service.resolve(event.id, uuid.uuid4(), "twice")

    @pytest.mark.asyncio
    async def test_acknowledge_after_resolve_rejected(self, db_session):
        service = EscalationService(db_session)
        event = await service.raise_escalation("agent:test", "t", "d")
        await service.resolve(event.id, uuid.uuid4(), "done")
        with pytest.raises(ValueError):
            await service.acknowledge(event.id, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_missing_event_raises(self, db_session):
        service = EscalationService(db_session)
        with pytest.raises(ValueError):
            await service.acknowledge(uuid.uuid4(), uuid.uuid4())
        with pytest.raises(ValueError):
            await service.resolve(uuid.uuid4(), uuid.uuid4(), "notes")


# ─── Orchestrator integration ────────────────────────────────────────────────

class TestOrchestratorHook:
    @pytest.mark.asyncio
    async def test_escalate_below_0_85_creates_p0_event(self, db_session, seeded_project, patch_agents):
        patch_agents(0.80)
        orchestrator = KimiClawOrchestrator(db_session)

        result = await orchestrator.advance_project(seeded_project.id, max_steps=3)
        assert result["advanced"] is False

        events = (await db_session.execute(select(EscalationEvent))).scalars().all()
        assert len(events) == 2  # both onboarding agents escalated
        assert all(e.priority == PRIORITY_P0 for e in events)
        assert all(e.source.startswith("agent:") for e in events)
        assert all(e.status == EscalationStatus.open for e in events)
        # Context package carries the queue linkage.
        assert all(e.context_package.get("queue_item_id") for e in events)

    @pytest.mark.asyncio
    async def test_human_review_tier_creates_p1_event(self, db_session, seeded_project, patch_agents):
        patch_agents(0.90)
        orchestrator = KimiClawOrchestrator(db_session)

        await orchestrator.advance_project(seeded_project.id, max_steps=3)

        events = (await db_session.execute(select(EscalationEvent))).scalars().all()
        assert len(events) == 2
        assert all(e.priority == PRIORITY_P1 for e in events)

    @pytest.mark.asyncio
    async def test_service_failure_does_not_break_dispatch(self, db_session, seeded_project, patch_agents, monkeypatch):
        patch_agents(0.80)

        async def _boom(*args, **kwargs):
            raise RuntimeError("service down")

        monkeypatch.setattr(
            "app.escalations.service.EscalationService.raise_escalation", _boom
        )
        orchestrator = KimiClawOrchestrator(db_session)
        result = await orchestrator.advance_project(seeded_project.id, max_steps=3)

        assert result["advanced"] is False
        items = (await db_session.execute(
            select(EscalationEvent)
        )).scalars().all()
        assert items == []  # hook failed gracefully


# ─── Celery jobs ─────────────────────────────────────────────────────────────

class TestEscalationJobs:
    @pytest.mark.asyncio
    async def test_p0_redispatch_until_success(self, db_session, patch_db_context):
        from app.tasks.escalation_jobs import dispatch_p0_escalations

        service = EscalationService(db_session)
        event = await service.raise_escalation(
            "agent:test", "p0", "d", priority=PRIORITY_P0
        )
        # Clear any sends from the raise path to simulate total channel failure.
        event.channels_sent = {}
        await db_session.commit()

        outcome = dispatch_p0_escalations()
        assert outcome == {"checked": 1, "redispatched": 1}
        await db_session.refresh(event)
        assert "email" in event.channels_sent  # attempted again (log-only adapters)

    @pytest.mark.asyncio
    async def test_p0_skipped_after_recent_success(self, db_session, patch_db_context):
        from app.tasks.escalation_jobs import dispatch_p0_escalations

        now = datetime.now(UTC)
        event = EscalationEvent(
            source="agent:test",
            title="p0",
            detail="d",
            priority=PRIORITY_P0,
            severity_score=0.95,
            status=EscalationStatus.open,
            channels_sent={
                "email": {
                    "sent_at": now.isoformat(),
                    "success": True,
                    "configured": True,
                    "detail": "",
                }
            },
        )
        db_session.add(event)
        await db_session.commit()

        outcome = dispatch_p0_escalations()
        assert outcome == {"checked": 1, "redispatched": 0}

    @pytest.mark.asyncio
    async def test_p1_job_dispatches_email_and_in_app(self, db_session, patch_db_context):
        from app.tasks.escalation_jobs import send_p1_escalations

        service = EscalationService(db_session)
        event = await service.raise_escalation(
            "agent:test", "p1", "d", priority=PRIORITY_P1
        )
        event.channels_sent = {}
        await db_session.commit()

        outcome = send_p1_escalations()
        assert outcome == {"checked": 1, "dispatched": 1}
        await db_session.refresh(event)
        assert set(event.channels_sent.keys()) == {"email", "in_app"}

    @pytest.mark.asyncio
    async def test_digest_aggregates_open_p2_and_recent_p0_p1(self, db_session, patch_db_context):
        from app.tasks.escalation_jobs import daily_escalation_digest

        service = EscalationService(db_session)
        await service.raise_escalation("agent:a", "p2 one", "d", priority=PRIORITY_P2)
        await service.raise_escalation("agent:b", "p2 two", "d", priority=PRIORITY_P2)
        await service.raise_escalation("agent:c", "p0", "d", priority=PRIORITY_P0)

        old = datetime.now(UTC) - timedelta(days=2)
        stale = EscalationEvent(
            source="agent:old",
            title="stale p0",
            detail="d",
            priority=PRIORITY_P0,
            severity_score=0.95,
            status=EscalationStatus.resolved,
            created_at=old,
        )
        db_session.add(stale)
        await db_session.commit()

        outcome = daily_escalation_digest()
        assert outcome["open_p2"] == 2
        assert outcome["open_p0"] == 1
        assert outcome["recent_24h_p0"] == 1
        assert outcome["recent_24h_p1"] == 0
        assert outcome["email_sent"] is False  # no SMTP/SES configured in tests


# ─── API ─────────────────────────────────────────────────────────────────────

class TestEscalationsAPI:
    @pytest.mark.asyncio
    async def test_list_with_filters_and_pagination(
        self, client: AsyncClient, db_session, operator_headers
    ):
        service = EscalationService(db_session)
        await service.raise_escalation("agent:a", "p0", "d", priority=PRIORITY_P0)
        await service.raise_escalation("agent:b", "p2", "d", priority=PRIORITY_P2)
        await service.raise_escalation("agent:c", "p2b", "d", priority=PRIORITY_P2)

        resp = await client.get("/api/v1/escalations/", headers=operator_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert body["items"][0]["id"]  # newest first

        resp = await client.get(
            "/api/v1/escalations/?priority=2", headers=operator_headers
        )
        assert resp.json()["total"] == 2

        resp = await client.get(
            "/api/v1/escalations/?status=open&skip=1&limit=1",
            headers=operator_headers,
        )
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 1

        resp = await client.get(
            f"/api/v1/escalations/?project_id={uuid.uuid4()}",
            headers=operator_headers,
        )
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_list_rejects_invalid_status(self, client: AsyncClient, operator_headers):
        resp = await client.get(
            "/api/v1/escalations/?status=bogus", headers=operator_headers
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_stats_endpoint(self, client: AsyncClient, db_session, operator_headers):
        service = EscalationService(db_session)
        await service.raise_escalation("agent:a", "p0", "d", priority=PRIORITY_P0)
        event = await service.raise_escalation("agent:b", "p2", "d", priority=PRIORITY_P2)
        await service.acknowledge(event.id, uuid.uuid4())

        resp = await client.get("/api/v1/escalations/stats", headers=operator_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["by_status"]["open"] == 1
        assert body["by_status"]["acknowledged"] == 1
        assert body["by_priority"]["0"] == 1
        assert body["by_priority"]["2"] == 1
        assert body["open_p0"] == 1
        assert body["avg_time_to_ack_seconds"] is not None

    @pytest.mark.asyncio
    async def test_get_by_id(self, client: AsyncClient, db_session, operator_headers):
        service = EscalationService(db_session)
        event = await service.raise_escalation(
            "agent:a", "title", "detail", context_package={"k": "v"}
        )
        resp = await client.get(
            f"/api/v1/escalations/{event.id}", headers=operator_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(event.id)
        assert body["title"] == "title"
        assert body["context_package"] == {"k": "v"}
        assert body["status"] == "open"
        assert "channels_sent" in body

        resp = await client.get(
            f"/api/v1/escalations/{uuid.uuid4()}", headers=operator_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_acknowledge_and_resolve_via_api(
        self, client: AsyncClient, db_session, operator_headers
    ):
        service = EscalationService(db_session)
        event = await service.raise_escalation("agent:a", "t", "d")

        resp = await client.post(
            f"/api/v1/escalations/{event.id}/acknowledge", headers=operator_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "acknowledged"
        assert resp.json()["acknowledged_by"] is not None

        resp = await client.post(
            f"/api/v1/escalations/{event.id}/resolve",
            json={"notes": "handled"},
            headers=operator_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "resolved"
        assert body["resolution_notes"] == "handled"

        # Double resolve → 409.
        resp = await client.post(
            f"/api/v1/escalations/{event.id}/resolve",
            json={"notes": "again"},
            headers=operator_headers,
        )
        assert resp.status_code == 409

        # Unknown id → 404.
        resp = await client.post(
            f"/api/v1/escalations/{uuid.uuid4()}/acknowledge",
            headers=operator_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_api_requires_operator_role(self, client: AsyncClient, engine):
        """Viewer-role token is rejected; unauthenticated requests are 401/403."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.auth.security import create_access_token

        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        viewer_id = uuid.uuid4()
        async with session_factory() as session:
            viewer = User(
                id=viewer_id,
                email=f"viewer{viewer_id.hex[:8]}@carbonverify.io",
                email_hash=compute_searchable_hash(f"viewer{viewer_id.hex[:8]}@carbonverify.io"),
                name="Viewer",
                role=UserRoleEnum.viewer,
                mfa_enabled=False,
                hashed_password="hashed",
            )
            session.add(viewer)
            await session.commit()
        viewer_headers = {"Authorization": f"Bearer {create_access_token(str(viewer_id))}"}

        resp = await client.get("/api/v1/escalations/", headers=viewer_headers)
        assert resp.status_code == 403

        resp = await client.get("/api/v1/escalations/")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_health_score(self, client: AsyncClient, db_session, operator_headers):
        service = EscalationService(db_session)
        await service.raise_escalation("agent:a", "p0", "d", priority=PRIORITY_P0)

        # One recent high-confidence decision for the confidence component.
        db_session.add(AgentDecision(
            decision_id=uuid.uuid4(),
            agent_type="validation",
            action="auto_advance",
            confidence_score=0.97,
            reasoning="r",
            actor="agent:validation",
            record_hash="0" * 64,
        ))
        await db_session.commit()

        resp = await client.get(
            "/api/v1/escalations/health/score", headers=operator_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert 0 <= body["score"] <= 100
        assert "components" in body
        assert body["components"]["agent_confidence"] == 97.0
        assert body["components"]["open_escalations"]["open_p0"] == 1
        assert body["components"]["review_queue_depth"]["pending"] == 0
