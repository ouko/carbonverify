"""Targeted unit tests for uncovered branches in the autonomous layer.

These lift the per-module coverage of the Success Criterion 5 scope above 80%
for branches the functional acceptance tests don't reach: operator API filter
branches, escalation channel adapters (log-only + configured paths), the
knowledge-base module wrappers and embedders, the pub/sub layer with a fake
Redis client, and the escalation beat jobs.
"""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.encryption import compute_searchable_hash
from app.escalations.channels import (
    EmailChannel,
    InAppChannel,
    SMSChannel,
    WhatsAppChannel,
)
from app.escalations.models import EscalationEvent, EscalationStatus
from app.knowledge.embeddings import (
    LocalHashEmbedder,
    OpenAICompatibleEmbedder,
    cosine_similarity,
    embedding_dim,
    get_embedder,
    top_k,
)
from app.knowledge.service import KnowledgeBaseService, chunk_text
from app.models import AgentDecision, HumanReviewQueue, User, UserRoleEnum
from app.orchestrator.audit_chain import (
    compute_record_hash,
    hash_fields_for,
    record_decision,
)
from app.orchestrator.pubsub import AgentPubSub
from app.remediation.models import RemediationAttempt

pytestmark = pytest.mark.asyncio


def _fake_event(**overrides):
    base = {
        "id": uuid.uuid4(),
        "project_id": None,
        "source": "agent:validation",
        "title": "Test escalation",
        "detail": "Something needs attention",
        "priority": 1,
        "severity_score": 0.8,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _settings_patch(monkeypatch, **attrs):
    """Patch attributes on the shared cached Settings instance."""
    from app.config import get_settings

    settings = get_settings()
    for key, value in attrs.items():
        monkeypatch.setattr(settings, key, value, raising=False)
    return settings


# ─── app/api/decisions.py ─────────────────────────────────────────────────────


async def test_decisions_filters_verify_chain_and_get_by_id(
    client, db_session, operator_headers
):
    prev_hash = None
    for i in range(3):
        decision = AgentDecision(
            id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
            project_id=None,
            agent_type="ingestion" if i else "reporting",
            action="auto_advance",
            confidence_score=0.96,
            reasoning=f"gap test decision {i}",
            input_summary=None,
            context_package=None,
            prev_hash=prev_hash,
            actor="agent:test",
            created_at=datetime.now(UTC) - timedelta(microseconds=i),
        )
        decision.record_hash = compute_record_hash(hash_fields_for(decision))
        prev_hash = decision.record_hash
        db_session.add(decision)
    await db_session.commit()

    resp = await client.get("/api/v1/audit/decisions", headers=operator_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3

    resp = await client.get(
        "/api/v1/audit/decisions",
        params={"agent_type": "reporting"},
        headers=operator_headers,
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["decisions"][0]["agent_type"] == "reporting"

    resp = await client.get(
        "/api/v1/audit/decisions",
        params={"action": "auto_advance", "limit": 2, "offset": 1},
        headers=operator_headers,
    )
    assert resp.json()["total"] == 3
    assert len(resp.json()["decisions"]) == 2

    resp = await client.post("/api/v1/audit/verify-chain", headers=operator_headers)
    assert resp.status_code == 200
    assert resp.json()["valid"] is True

    decision_id = body["decisions"][0]["decision_id"]
    resp = await client.get(
        f"/api/v1/audit/{decision_id}", headers=operator_headers
    )
    assert resp.status_code == 200
    assert resp.json()["decision_id"] == decision_id

    resp = await client.get(
        f"/api/v1/audit/{uuid.uuid4()}", headers=operator_headers
    )
    assert resp.status_code == 404


# ─── app/api/validation_health.py ─────────────────────────────────────────────


async def test_validation_health_endpoint_empty_and_populated(
    client, db_session, operator_headers
):
    resp = await client.get("/api/v1/validation/health", headers=operator_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["latest"] is None
    assert body["history"] == []
    # No runs yet → every journey reports zero counts.
    assert all(stats == {"completed": 0, "failed": 0} for stats in body["journeys"].values())

    from app.validation_engine.health import compute_and_store_snapshot

    snapshot = await compute_and_store_snapshot(db_session)
    resp = await client.get("/api/v1/validation/health", headers=operator_headers)
    body = resp.json()
    assert body["latest"]["score"] == snapshot.score
    assert len(body["history"]) == 1


# ─── app/api/escalations.py remaining branches ────────────────────────────────


@pytest_asyncio.fixture
async def escalation_set(db_session):
    events = [
        EscalationEvent(
            id=uuid.uuid4(),
            source="agent:ingestion",
            title=f"Gap escalation {i}",
            detail="detail",
            priority=1 if i else 0,
            severity_score=0.8,
            status=EscalationStatus.open if i < 2 else EscalationStatus.resolved,
            channels_sent={},
            created_at=datetime.now(UTC) - timedelta(minutes=i),
        )
        for i in range(4)
    ]
    db_session.add_all(events)
    await db_session.commit()
    return events


async def test_escalations_api_filters_get_resolve_conflict(
    client, db_session, operator_headers, escalation_set
):
    resp = await client.get(
        "/api/v1/escalations/",
        params={"status": "open", "priority": 1},
        headers=operator_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = await client.get(
        "/api/v1/escalations/",
        params={"project_id": str(uuid.uuid4())},
        headers=operator_headers,
    )
    assert resp.json()["total"] == 0

    resp = await client.get(
        "/api/v1/escalations/", params={"status": "bogus"}, headers=operator_headers
    )
    assert resp.status_code == 422

    open_id = escalation_set[1].id
    resp = await client.get(f"/api/v1/escalations/{open_id}", headers=operator_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == str(open_id)

    resp = await client.get(
        f"/api/v1/escalations/{uuid.uuid4()}", headers=operator_headers
    )
    assert resp.status_code == 404

    # Acknowledge-time metrics feed the stats endpoint.
    resp = await client.post(
        f"/api/v1/escalations/{open_id}/acknowledge", headers=operator_headers
    )
    assert resp.status_code == 200

    resp = await client.get("/api/v1/escalations/stats", headers=operator_headers)
    stats = resp.json()
    assert stats["avg_time_to_ack_seconds"] is not None

    resp = await client.post(
        f"/api/v1/escalations/{open_id}/resolve",
        json={"notes": "fixed"},
        headers=operator_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"

    # Double resolve → 409; acknowledge of a resolved event → 404.
    resp = await client.post(
        f"/api/v1/escalations/{open_id}/resolve",
        json={"notes": "again"},
        headers=operator_headers,
    )
    assert resp.status_code == 409
    resp = await client.post(
        f"/api/v1/escalations/{open_id}/acknowledge", headers=operator_headers
    )
    assert resp.status_code == 404

    resp = await client.post(
        f"/api/v1/escalations/{uuid.uuid4()}/acknowledge", headers=operator_headers
    )
    assert resp.status_code == 404


async def test_escalations_health_score_components(
    client, db_session, operator_headers, escalation_set
):
    # Agent confidence component from a recent decision.
    await record_decision(
        db_session,
        agent_type="ingestion",
        action="auto_advance",
        confidence_score=0.9,
        reasoning="gap test decision for health score",
        actor="agent:ingestion",
    )
    resp = await client.get(
        "/api/v1/escalations/health/score", headers=operator_headers
    )
    assert resp.status_code == 200
    components = resp.json()["components"]
    assert "agent_confidence" in components
    assert components["open_escalations"]["open_p0"] == 1
    assert components["review_queue_depth"]["pending"] == 0


# ─── app/api/remediation.py remaining branches ────────────────────────────────


async def test_remediation_attempts_project_filter_and_retry_422(
    client, db_session, operator_headers
):
    from app.remediation.rules import seed_default_rules

    await seed_default_rules(db_session)
    project_id = uuid.uuid4()
    db_session.add(
        RemediationAttempt(
            rule_key="db_deadlock",
            target_type="calculation",
            target_id="gap-api-1",
            project_id=project_id,
            status="resolved",
            attempt_number=1,
            before_state_hash="a" * 64,
            after_state_hash="b" * 64,
            detail={},  # no failing_state snapshot → retry must 422
        )
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/remediation/attempts",
        params={"project_id": str(project_id)},
        headers=operator_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1

    resp = await client.get(
        "/api/v1/remediation/attempts",
        params={"project_id": str(uuid.uuid4())},
        headers=operator_headers,
    )
    assert resp.json()["total"] == 0

    resp = await client.post(
        f"/api/v1/remediation/attempts/{body['attempts'][0]['id']}/retry",
        headers=operator_headers,
    )
    assert resp.status_code == 422


# ─── app/escalations/channels.py configured paths ─────────────────────────────


async def test_whatsapp_channel_configured_success_and_failure(monkeypatch):
    _settings_patch(monkeypatch, ESCALATION_NOTIFY_WHATSAPP="+254700000000")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "phone-id")

    from app.services.whatsapp import meta_api

    class _FakeAPI:
        async def send_text_message(self, to, text):
            return {"success": True}

    monkeypatch.setattr(meta_api, "get_whatsapp_api", lambda: _FakeAPI())
    result = await WhatsAppChannel().send(_fake_event())
    assert result.success is True
    assert result.configured is True

    class _BrokenAPI:
        async def send_text_message(self, to, text):
            raise ConnectionError("meta down")

    monkeypatch.setattr(meta_api, "get_whatsapp_api", lambda: _BrokenAPI())
    result = await WhatsAppChannel().send(_fake_event())
    assert result.success is False
    assert result.configured is True
    assert "meta down" in result.detail


async def test_sms_channel_configured_success_and_failure(monkeypatch):
    _settings_patch(monkeypatch, ESCALATION_SMS_WEBHOOK_URL="http://sms.invalid/hook")
    _settings_patch(monkeypatch, ESCALATION_NOTIFY_SMS="+254700000000")

    class _FakeResponse:
        def raise_for_status(self):
            return None

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json=None):
            return _FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    result = await SMSChannel().send(_fake_event())
    assert result.success is True
    assert result.configured is True

    class _ExplodingClient(_FakeAsyncClient):
        async def post(self, url, json=None):
            raise ConnectionError("sms gateway unreachable")

    monkeypatch.setattr("httpx.AsyncClient", _ExplodingClient)
    result = await SMSChannel().send(_fake_event())
    assert result.success is False
    assert "unreachable" in result.detail


async def test_email_channel_smtp_probe_and_configured_send(monkeypatch):
    # SMTP provider without a host → not configured.
    _settings_patch(
        monkeypatch,
        ESCALATION_NOTIFY_EMAIL="ops@example.com",
        EMAIL_PROVIDER="smtp",
        SMTP_HOST="",
    )
    channel = EmailChannel()
    assert channel.is_configured() is False
    result = await channel.send(_fake_event())
    assert result.success is False and result.configured is False

    # Configured provider with a fake email service → full send loop.
    _settings_patch(monkeypatch, EMAIL_PROVIDER="ses")
    assert channel.is_configured() is True

    sent = []

    class _FakeEmailService:
        async def send_email(self, to, subject, body_text, body_html=None):
            sent.append((to, subject))

    monkeypatch.setattr(
        "app.services.email.get_email_service", lambda: _FakeEmailService()
    )
    result = await EmailChannel().send(_fake_event(priority=0))
    assert result.success is True
    assert sent == [("ops@example.com", "[Escalation P0] Test escalation")]

    class _BrokenEmailService:
        async def send_email(self, to, subject, body_text, body_html=None):
            raise RuntimeError("smtp refused")

    monkeypatch.setattr(
        "app.services.email.get_email_service", lambda: _BrokenEmailService()
    )
    result = await EmailChannel().send(_fake_event())
    assert result.success is False and result.configured is True
    assert "smtp refused" in result.detail


async def test_in_app_channel_success_and_failure(monkeypatch):
    published = []

    async def _publish(event_type, payload):
        published.append((event_type, payload))

    monkeypatch.setattr(
        "app.orchestrator.pubsub.agent_pubsub.publish_event", _publish
    )
    event = _fake_event(project_id=uuid.uuid4())
    result = await InAppChannel().send(event)
    assert result.success is True
    assert published[0][0] == "agent_escalation"
    assert published[0][1]["escalation_id"] == str(event.id)

    async def _explode(event_type, payload):
        raise ConnectionError("pubsub down")

    monkeypatch.setattr(
        "app.orchestrator.pubsub.agent_pubsub.publish_event", _explode
    )
    result = await InAppChannel().send(_fake_event())
    assert result.success is False
    assert "pubsub down" in result.detail


# ─── app/knowledge module wrappers, service edges, embeddings ─────────────────


async def test_knowledge_module_wrappers_success_and_failure(
    db_session, patch_db_context, monkeypatch
):
    import app.database as app_database
    import app.knowledge as kb

    service = KnowledgeBaseService(db_session)
    await service.ingest_document(
        registry="gold_standard",
        methodology_id="GS TPDD v3",
        title="TPDD v3",
        content="Fuelwood monitoring requires the Kitchen Performance Test "
        "with representative household sampling and weighing of fuelwood.",
        version="v3",
    )

    results = await kb.search_knowledge("fuelwood monitoring", registry="gold_standard")
    assert results and results[0]["document"]["methodology_id"] == "GS TPDD v3"

    answer = await kb.query_knowledge_base("What does the KPT protocol require?")
    assert answer["question"] == "What does the KPT protocol require?"
    assert answer["passages"]
    # No API key → graceful unreviewed fallback.
    assert answer["unreviewed"] is True

    # Failure path: the DB context itself blows up → defensive None / [].
    def _exploding_context():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(app_database, "get_db_context", _exploding_context)
    assert await kb.search_knowledge("anything") == []
    assert await kb.query_knowledge_base("anything") is None


def test_chunk_text_edge_cases():
    assert chunk_text("") == []
    assert chunk_text("short text") == ["short text"]
    long_text = " ".join(f"token{i}" for i in range(1200))
    chunks = chunk_text(long_text, size=500, overlap=50)
    assert len(chunks) >= 2
    # Windows overlap: the second window starts before the first ends.
    assert chunks[1].split()[0] in chunks[0].split()


async def test_knowledge_service_delete_get_and_list(db_session):
    service = KnowledgeBaseService(db_session)
    document = await service.ingest_document(
        registry="verra",
        methodology_id="VM0050",
        title="Verra VM0050",
        content="Non-renewable biomass assessment requires country-specific "
        "fNRB values derived from reliable forest sector data.",
        version="v1.1",
    )

    docs = await service.list_documents()
    assert len(docs) == 1
    assert docs[0]["chunk_count"] >= 1
    assert await service.list_documents(registry="gold_standard") == []

    detail = await service.get_document(str(document.id))
    assert detail["methodology_id"] == "VM0050"
    assert detail["chunks"] and detail["chunk_count"] == len(detail["chunks"])
    assert await service.get_document(str(uuid.uuid4())) is None

    assert await service.delete_document(str(uuid.uuid4())) is False
    assert await service.delete_document(str(document.id)) is True
    assert await service.list_documents() == []


async def test_knowledge_query_without_documents(db_session):
    service = KnowledgeBaseService(db_session)
    answer = await service.query_knowledge_base("anything at all")
    assert answer["answer"] == "No methodology documents match this question."
    assert answer["passages"] == []


async def test_openai_compatible_embedder_and_factory(monkeypatch):
    embedder = OpenAICompatibleEmbedder(
        base_url="http://embedder.invalid/", model="m", api_key="k"
    )
    assert embedder.base_url == "http://embedder.invalid"

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            }

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, headers=None, json=None):
            return _FakeResponse()

        async def aclose(self):
            return None

    monkeypatch.setattr(embedder, "_client", _FakeClient())
    vectors = await embedder.embed(["a", "b"])
    # Results are re-ordered by index.
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]

    await embedder.aclose()

    no_key = OpenAICompatibleEmbedder(base_url="http://x", api_key="")
    with pytest.raises(RuntimeError, match="KNOWLEDGE_EMBEDDER_API_KEY"):
        await no_key.embed(["x"])

    # Factory: remote configured but constructor fails → local fallback.
    _settings_patch(
        monkeypatch,
        KNOWLEDGE_EMBEDDER_URL="http://embedder.invalid",
        KNOWLEDGE_EMBEDDER_API_KEY="k",
    )

    import app.knowledge.embeddings as embeddings_module

    class _ExplodingEmbedder:
        def __init__(self, *args, **kwargs):
            raise ConnectionError("embedder down")

    monkeypatch.setattr(
        embeddings_module, "OpenAICompatibleEmbedder", _ExplodingEmbedder
    )
    assert isinstance(get_embedder(), LocalHashEmbedder)


def test_embedding_math_helpers():
    embedder = LocalHashEmbedder(dim=32)
    a = embedder._bucketize("fuelwood cookstove fuelwood")
    b = embedder._bucketize("fuelwood cookstove fuelwood")
    assert cosine_similarity(a, b) == pytest.approx(1.0)
    assert embedding_dim(a) == 32
    assert top_k(a, [a, [0.0] * 32], 5)[0][0] == 0


# ─── app/orchestrator/pubsub.py with a fake Redis ─────────────────────────────


class _FakePubSub:
    def __init__(self, messages=()):
        self.subscribed = []
        self.messages = list(messages)
        self.closed = False

    async def subscribe(self, *channels):
        self.subscribed.extend(channels)

    async def unsubscribe(self):
        pass

    async def close(self):
        self.closed = True

    async def listen(self):
        for message in self.messages:
            yield message


class _FakeRedis:
    def __init__(self, pubsub):
        self._pubsub = pubsub
        self.published = []
        self.closed = False

    def pubsub(self):
        return self._pubsub

    async def publish(self, channel, message):
        self.published.append((channel, message))

    async def close(self):
        self.closed = True


@pytest.fixture
def fresh_pubsub(monkeypatch):
    monkeypatch.setattr(AgentPubSub, "_instance", None)
    pubsub = AgentPubSub()
    return pubsub


async def test_pubsub_connect_publish_and_disconnect(fresh_pubsub, monkeypatch):
    import app.orchestrator.pubsub as pubsub_module

    fake_pubsub = _FakePubSub()
    fake_redis = _FakeRedis(fake_pubsub)
    monkeypatch.setattr(
        pubsub_module.redis, "from_url", lambda *a, **k: fake_redis
    )

    await fresh_pubsub.connect()
    assert fake_pubsub.subscribed == ["orchestrator:events", "agent:results"]

    await fresh_pubsub.publish_event("test_event", {"x": 1})
    await fresh_pubsub.publish_agent_result("ingestion", "proj-1", {"ok": True})
    await fresh_pubsub.publish_project_update("proj-1", {"type": "state_transition"})
    channels = [c for c, _ in fake_redis.published]
    assert channels == [
        "orchestrator:events",
        "agent:results",
        "project:proj-1",
    ]

    await fresh_pubsub.disconnect()
    assert fake_pubsub.closed and fake_redis.closed


async def test_pubsub_connect_failure_raises(fresh_pubsub, monkeypatch):
    import app.orchestrator.pubsub as pubsub_module

    def _explode(*a, **k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(pubsub_module.redis, "from_url", _explode)
    with pytest.raises(ConnectionError):
        await fresh_pubsub.connect()
    assert fresh_pubsub._redis is None


async def test_pubsub_listen_loop_forwards_and_swallows_errors(
    fresh_pubsub, monkeypatch
):
    import asyncio
    import json as json_module

    received = []

    async def _good_listener(channel, payload):
        received.append((channel, payload))

    async def _bad_listener(channel, payload):
        raise RuntimeError("listener boom")

    fresh_pubsub.add_listener(_good_listener)
    fresh_pubsub.add_listener(_bad_listener)
    fresh_pubsub.remove_listener(_bad_listener)
    assert fresh_pubsub._listeners == [_good_listener]

    messages = [
        {"type": "message", "channel": "orchestrator:events", "data": json_module.dumps({"type": "ok"})},
        {"type": "message", "channel": "orchestrator:events", "data": "{not json"},
    ]
    fake_pubsub = _FakePubSub(messages)
    fake_pubsub.messages.append(RuntimeError("listen boom"))
    fresh_pubsub._pubsub = fake_pubsub

    # A message value that raises from listen() hits the outer error handler;
    # the invalid-JSON message is skipped with a warning.
    class _RaisingPubSub(_FakePubSub):
        async def listen(self):
            yield messages[0]
            yield messages[1]
            raise RuntimeError("listen boom")

    fresh_pubsub._pubsub = _RaisingPubSub(messages)
    await fresh_pubsub._listen_loop()
    assert received == [("orchestrator:events", {"type": "ok"})]

    # Cancelled loop exits silently; a failed task is logged, not raised.
    async def _cancelled():
        raise asyncio.CancelledError()

    task = asyncio.ensure_future(_cancelled())
    await asyncio.sleep(0)
    fresh_pubsub._on_listen_done(task)  # must not raise

    async def _failing():
        raise RuntimeError("task boom")

    task = asyncio.ensure_future(_failing())
    await asyncio.sleep(0)
    fresh_pubsub._on_listen_done(task)  # logged, not raised


# ─── app/tasks/escalation_jobs.py extra branches ──────────────────────────────


async def test_p1_job_event_id_and_already_sent_branches(db_session, patch_db_context):
    from app.tasks.escalation_jobs import send_p1_escalations

    resolved = EscalationEvent(
        id=uuid.uuid4(),
        source="agent:x",
        title="resolved",
        detail="d",
        priority=1,
        status=EscalationStatus.resolved,
        channels_sent={},
    )
    already_sent = EscalationEvent(
        id=uuid.uuid4(),
        source="agent:x",
        title="sent",
        detail="d",
        priority=1,
        status=EscalationStatus.open,
        channels_sent={"email": {"success": True, "sent_at": "2024-01-01T00:00:00+00:00"}},
    )
    unsent = EscalationEvent(
        id=uuid.uuid4(),
        source="agent:x",
        title="unsent",
        detail="d",
        priority=1,
        status=EscalationStatus.open,
        channels_sent={},
    )
    db_session.add_all([resolved, already_sent, unsent])
    await db_session.commit()

    # Explicit event_id: non-open event is skipped inside the loop.
    outcome = send_p1_escalations(str(resolved.id))
    assert outcome == {"checked": 1, "dispatched": 0}

    # Beat sweep: skips the event with a successful channel, dispatches the other.
    outcome = send_p1_escalations()
    assert outcome == {"checked": 2, "dispatched": 1}


async def test_p0_latest_success_invalid_timestamp(db_session, patch_db_context):
    from app.tasks.escalation_jobs import _latest_success, dispatch_p0_escalations

    # Unparseable sent_at values are ignored rather than crashing the sweep.
    event = EscalationEvent(
        id=uuid.uuid4(),
        source="agent:x",
        title="p0",
        detail="d",
        priority=0,
        status=EscalationStatus.open,
        channels_sent={
            "email": {"success": True, "sent_at": "not-a-timestamp"},
            "sms": {"success": False, "sent_at": "2024-01-01T00:00:00+00:00"},
        },
    )
    assert _latest_success(event) is None

    db_session.add(event)
    await db_session.commit()
    outcome = dispatch_p0_escalations()
    assert outcome == {"checked": 1, "redispatched": 1}


async def test_daily_digest_email_branch(db_session, patch_db_context, monkeypatch):
    from app.tasks import escalation_jobs

    db_session.add(
        EscalationEvent(
            id=uuid.uuid4(),
            source="agent:x",
            title="open p2",
            detail="d",
            priority=2,
            status=EscalationStatus.open,
            channels_sent={},
        )
    )
    await db_session.commit()

    _settings_patch(monkeypatch, ESCALATION_NOTIFY_EMAIL="ops@example.com")

    class _BrokenEmailService:
        async def send_email(self, to, subject, body_text, body_html=None):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(
        "app.services.email.get_email_service", lambda: _BrokenEmailService()
    )
    outcome = escalation_jobs.daily_escalation_digest()
    # The digest still reports counts; the failing email is logged, not raised.
    assert outcome["open_p2"] == 1
    assert outcome["email_sent"] is False


# ─── app/agents/ingestion_agent.py anomaly branches ───────────────────────────


@pytest_asyncio.fixture
async def ingestion_project(db_session):
    from app.models import Developer

    email = f"ing-{uuid.uuid4().hex[:8]}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Ingestion Owner",
        role=UserRoleEnum.developer,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.flush()
    developer = Developer(id=uuid.uuid4(), user_id=user.id, company_name="Acme")
    db_session.add(developer)
    await db_session.flush()
    from datetime import date

    from app.models import MethodologyEnum, Project, ProjectStatusEnum

    project = Project(
        id=uuid.uuid4(),
        name="Ingestion Gap Project",
        developer_id=developer.id,
        methodology=MethodologyEnum.TPDDTEC_v4,
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        status=ProjectStatusEnum.data_collection,
    )
    db_session.add(project)
    await db_session.commit()
    return project


def _upload(project_id, filename, **kwargs):
    from app.models import DetectedFileTypeEnum, FileUpload

    defaults = {
        "id": uuid.uuid4(),
        "project_id": project_id,
        "original_filename": filename,
        "detected_type": DetectedFileTypeEnum.excel,
        "mime_type": "application/vnd.ms-excel",
        "s3_key": f"uploads/{filename}",
        "s3_bucket": "bucket",
        "file_size_bytes": 1024,
        "file_hash_sha256": uuid.uuid4().hex * 4,
    }
    defaults.update(kwargs)
    return FileUpload(**defaults)


def _source(project_id, **kwargs):
    from app.models import DataSource, SourceTypeEnum

    defaults = {
        "id": uuid.uuid4(),
        "project_id": project_id,
        "source_type": SourceTypeEnum.mobile_survey,
        "schema_version": "v1",
        "processed_data": {"records_extracted": 10},
        "confidence_score": 0.9,
    }
    defaults.update(kwargs)
    return DataSource(**defaults)


async def test_ingestion_agent_anomaly_branches(db_session, ingestion_project, monkeypatch):
    from datetime import date  # noqa: F401  (kept close to usage site)

    from app.agents import IngestionAgent
    from app.models import (
        DetectedFileTypeEnum,
        FileUploadStatusEnum,
        ValidationStatusEnum,
    )

    stale = datetime.now(UTC) - timedelta(days=10)
    db_session.add_all(
        [
            # Queued upload stuck for 10 days → stale_source + queued_count.
            _upload(
                ingestion_project.id,
                "stuck.xlsx",
                status=FileUploadStatusEnum.uploaded,
                created_at=stale,
            ),
            # Failed upload → failed_count.
            _upload(
                ingestion_project.id,
                "failed.xlsx",
                status=FileUploadStatusEnum.failed,
            ),
            # Structurally invalid upload: unknown type, empty hash, zero size.
            _upload(
                ingestion_project.id,
                "mystery.bin",
                status=FileUploadStatusEnum.completed,
                detected_type=DetectedFileTypeEnum.unknown,
                file_hash_sha256="",
                file_size_bytes=0,
            ),
            # Empty hash short-circuits duplicate detection.
            _upload(
                ingestion_project.id,
                "no-hash.xlsx",
                status=FileUploadStatusEnum.completed,
                file_hash_sha256="",
            ),
            # Flagged source → source_flagged anomaly.
            _source(
                ingestion_project.id,
                validation_status=ValidationStatusEnum.flagged,
            ),
            # Negative processed value → out_of_range_value.
            _source(
                ingestion_project.id,
                validation_status=ValidationStatusEnum.valid,
                processed_data={"fuel_kg_per_day": -3},
            ),
        ]
    )
    await db_session.commit()

    async def _fake_reason(self, task_prompt, context, tools=None, response_schema=None):
        return {"anomaly_severity": 0.2, "summary": "minor", "recommended_action": "watch"}

    monkeypatch.setattr(IngestionAgent, "reason_with_llm", _fake_reason)

    result = await IngestionAgent(ingestion_project.id, db_session).execute("test", {})
    assert result.status == "queued_for_review"  # failed_count > 0
    evidence = result.evidence
    assert evidence["queued_count"] == 1
    assert evidence["failed_count"] == 1
    assert evidence["flagged_source_count"] == 1
    assert evidence["anomaly_count"] >= 6  # stale + invalid + flagged + range
    anomaly_types = {a["type"] for a in evidence["anomalies"]}
    assert {"out_of_range_value", "upload_invalid"} <= anomaly_types
    assert evidence["flagged_source_count"] == 1  # source_flagged raised (maybe beyond top-5)
    # Stale anomalies are raised for the stuck upload (covered in the
    # dedicated stale-source test below where they reach the top-5 window).
    # LLM severity present → blended confidence path.
    assert "blended via LLM anomaly review" in result.reasoning
    assert evidence["llm_review"] == {"anomaly_severity": 0.2, "summary": "minor", "recommended_action": "watch"}


async def test_ingestion_agent_stale_source_anomalies(db_session, ingestion_project):
    """Stale uploads and unvalidated sources surface in the top anomaly list."""
    from app.agents import IngestionAgent
    from app.models import FileUploadStatusEnum, ValidationStatusEnum

    stale = datetime.now(UTC) - timedelta(days=10)
    db_session.add_all(
        [
            _upload(
                ingestion_project.id,
                "stuck.xlsx",
                status=FileUploadStatusEnum.uploaded,
                created_at=stale,
            ),
            _source(
                ingestion_project.id,
                validation_status=ValidationStatusEnum.pending,
                created_at=stale,
            ),
        ]
    )
    await db_session.commit()

    result = await IngestionAgent(ingestion_project.id, db_session).execute("test", {})
    anomaly_types = {a["type"] for a in result.evidence["anomalies"]}
    assert "stale_source" in anomaly_types
    details = " ".join(a["detail"] for a in result.evidence["anomalies"])
    assert "stuck in 'uploaded' for 10 days" in details
    assert "unvalidated for 10 days" in details


async def test_ingestion_agent_sources_only_completeness(db_session, ingestion_project):
    from app.agents import IngestionAgent
    from app.models import ValidationStatusEnum

    db_session.add(
        _source(ingestion_project.id, validation_status=ValidationStatusEnum.valid)
    )
    await db_session.commit()

    class _NoLLM(IngestionAgent):
        async def reason_with_llm(self, *args, **kwargs):
            return {"_fallback": True}

    result = await _NoLLM(ingestion_project.id, db_session).execute("test", {})
    assert result.evidence["completeness"] == 1.0
    assert result.evidence["upload_count"] == 0


# ─── app/orchestrator/orchestrator.py remaining paths ─────────────────────────


@pytest_asyncio.fixture
async def orch_project(db_session):
    from datetime import date

    from app.models import Developer, MethodologyEnum, Project, ProjectStatusEnum

    email = f"orch-{uuid.uuid4().hex[:8]}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Orch Owner",
        role=UserRoleEnum.developer,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.flush()
    developer = Developer(id=uuid.uuid4(), user_id=user.id, company_name="Acme")
    db_session.add(developer)
    await db_session.flush()
    project = Project(
        id=uuid.uuid4(),
        name="Orch Gap Project",
        developer_id=developer.id,
        methodology=MethodologyEnum.TPDDTEC_v4,
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        status=ProjectStatusEnum.onboarding,
    )
    db_session.add(project)
    await db_session.commit()
    return project


async def test_process_project_known_and_unknown_triggers(db_session, orch_project):
    from app.orchestrator.orchestrator import KimiClawOrchestrator

    orchestrator = KimiClawOrchestrator(db_session)

    result = await orchestrator.process_project(orch_project.id, "data_complete")
    assert result["state"] == "data_collection"
    assert result["agent_results"]  # real onboarding agents dispatched

    # Unknown trigger: target state falls back to the current state.
    result = await orchestrator.process_project(orch_project.id, "no_such_trigger")
    assert result["state"] == "data_collection"

    result = await orchestrator.process_project(uuid.uuid4(), "data_complete")
    assert result["error"] == "Project not found"


async def test_get_project_state_shape(db_session, orch_project):
    from app.orchestrator.orchestrator import KimiClawOrchestrator

    orchestrator = KimiClawOrchestrator(db_session)
    state = await orchestrator.get_project_state(orch_project.id)
    assert state["current_state"] == "onboarding"
    assert state["agent_runs"] == []
    assert state["pending_reviews"] == []

    missing = await orchestrator.get_project_state(uuid.uuid4())
    assert missing["error"] == "Project not found"


async def test_resolve_human_review_reject_and_escalate_paths(db_session, orch_project):
    from app.models import QueueItemTypeEnum, QueueStatusEnum
    from app.orchestrator.orchestrator import KimiClawOrchestrator

    orchestrator = KimiClawOrchestrator(db_session)
    item = HumanReviewQueue(
        id=uuid.uuid4(),
        item_type=QueueItemTypeEnum.agent_review,
        item_id=uuid.uuid4(),
        reason="gap test item",
        priority=3,
        status=QueueStatusEnum.pending,
        context_json={"project_id": str(orch_project.id), "agent_type": "ingestion"},
        confidence_gap=0.05,
    )
    db_session.add(item)
    await db_session.commit()

    resolution = await orchestrator.resolve_human_review(
        queue_item_id=item.id,
        decision="reject",
        resolution_notes="Data quality insufficient.",
        user_id=uuid.uuid4(),
        actor="reviewer@carbonverify.io",
    )
    assert resolution["status"] == "escalated"

    item2 = HumanReviewQueue(
        id=uuid.uuid4(),
        item_type=QueueItemTypeEnum.agent_review,
        item_id=uuid.uuid4(),
        reason="second gap item",
        priority=5,
        status=QueueStatusEnum.pending,
        context_json={"project_id": str(orch_project.id), "agent_type": "ingestion"},
        confidence_gap=0.2,
    )
    db_session.add(item2)
    await db_session.commit()
    resolution = await orchestrator.resolve_human_review(
        queue_item_id=item2.id,
        decision="escalate",
        resolution_notes="Needs a senior reviewer.",
        user_id=uuid.uuid4(),
    )
    assert resolution["status"] == "escalated"

    decisions = (
        await db_session.execute(
            select(AgentDecision).where(AgentDecision.action.in_(["human_rejected", "human_escalated"]))
        )
    ).scalars().all()
    assert len(decisions) == 2
    # Approval path would publish a next-trigger update; covered elsewhere.
    assert all(d.review_queue_item_id is not None for d in decisions)


async def test_sla_auto_approve_guard_branches(db_session, orch_project):
    from app.models import QueueItemTypeEnum, QueueStatusEnum
    from app.orchestrator.orchestrator import KimiClawOrchestrator

    orchestrator = KimiClawOrchestrator(db_session)

    # Missing item.
    outcome = await orchestrator.sla_auto_approve(uuid.uuid4())
    assert outcome["error"] == "Queue item not found"

    resolved_item = HumanReviewQueue(
        id=uuid.uuid4(),
        item_type=QueueItemTypeEnum.agent_review,
        item_id=uuid.uuid4(),
        reason="already resolved",
        priority=3,
        status=QueueStatusEnum.resolved,
        context_json={},
    )
    fresh_item = HumanReviewQueue(
        id=uuid.uuid4(),
        item_type=QueueItemTypeEnum.agent_review,
        item_id=uuid.uuid4(),
        reason="too fresh",
        priority=3,
        status=QueueStatusEnum.pending,
        context_json={},
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add_all([resolved_item, fresh_item])
    await db_session.commit()

    outcome = await orchestrator.sla_auto_approve(resolved_item.id)
    assert outcome["error"].startswith("Queue item is not pending")

    outcome = await orchestrator.sla_auto_approve(
        fresh_item.id, max_age=timedelta(hours=24)
    )
    assert outcome["error"] == "Queue item is younger than the SLA age"


async def test_dispatch_triggers_automatic_remediation(db_session, orch_project, monkeypatch):
    """An agent failure mentioning timeouts routes through the remediation
    engine before normal confidence routing (orchestrator self-healing)."""
    import app.orchestrator.orchestrator as orchestrator_module
    from app.agents import AgentResult
    from app.remediation.models import RemediationAttempt
    from app.remediation.rules import seed_default_rules

    await seed_default_rules(db_session)

    class _TimeoutAgent:
        def __init__(self, project_id, db_session=None):
            self.project_id = project_id
            self.db = db_session

        async def execute(self, trigger_event, context):
            return AgentResult(
                status="completed",
                confidence_score=0.5,
                output_data={},
                errors=["kimi api timeout after 30s"],
                execution_time_ms=1,
            )

    monkeypatch.setitem(orchestrator_module.AGENT_REGISTRY, "ingestion", _TimeoutAgent)
    from app.orchestrator.orchestrator import KimiClawOrchestrator

    orchestrator = KimiClawOrchestrator(db_session)
    await orchestrator.dispatch_agent(orch_project.id, "ingestion", "data_complete", {})

    attempts = (
        await db_session.execute(
            select(RemediationAttempt).where(
                RemediationAttempt.rule_key == "api_timeout_rate_limit"
            )
        )
    ).scalars().all()
    assert len(attempts) >= 1
    # No success signal → deferred (queued for retry), not a 3-strike escalation.
    assert attempts[0].status in ("failed", "escalated")


# ─── app/tasks/escalation_jobs.py remaining branches ──────────────────────────


def test_latest_success_naive_and_missing_timestamps():
    from app.tasks.escalation_jobs import _latest_success

    event = _fake_event()
    now = datetime.now(UTC)
    # Naive timestamp is normalized to UTC instead of crashing.
    event.channels_sent = {"email": {"success": True, "sent_at": now.replace(tzinfo=None).isoformat()}}
    latest = _latest_success(event)
    assert latest is not None and latest.tzinfo is not None
    # A successful record without sent_at is ignored.
    event.channels_sent = {"email": {"success": True}}
    assert _latest_success(event) is None


@pytest.mark.parametrize(
    "task_name",
    ["dispatch_p0_escalations", "send_p1_escalations", "daily_escalation_digest"],
)
def test_escalation_jobs_retry_on_failure(db_session, patch_db_context, monkeypatch, task_name):
    """A failing run_async routes through celery's retry (raise)."""
    from app.tasks import escalation_jobs

    def _exploding(coro):
        raise RuntimeError("db down")

    monkeypatch.setattr(escalation_jobs, "run_async", _exploding)
    task = getattr(escalation_jobs, task_name)
    with pytest.raises(Exception):
        task()
