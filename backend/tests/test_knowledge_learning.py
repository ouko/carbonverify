"""Tests for the Phase 5 methodology knowledge base and agent learning loop."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, update

import app.knowledge as knowledge_pkg
import app.orchestrator.orchestrator as orchestrator_module
from app.agents import AgentResult
from app.core.encryption import compute_searchable_hash
from app.knowledge.embeddings import LocalHashEmbedder, top_k
from app.knowledge.models import KnowledgeChunk, MethodologyDocument
from app.knowledge.service import KnowledgeBaseService
from app.learning.models import LearningReport
from app.learning.service import LearningLoopService, get_effective_threshold
from app.models import (
    AgentDecision,
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
from app.orchestrator.audit_chain import record_decision
from app.orchestrator.orchestrator import KimiClawOrchestrator

# ─── Knowledge base: ingest / embeddings / search ────────────────────────────

COOKSTOVE_CONTENT = (
    "Improved cookstoves methodologies require demonstration of thermal "
    "efficiency gains over the baseline three stone fire. Fuel consumption "
    "monitoring must follow the Kitchen Performance Test protocol with "
    "weighing of fuelwood across a representative sample of households. "
    "The methodology defines the fraction of non-renewable biomass saved "
    "through reduced fuelwood demand, and requires leakage assessment for "
    "shifted fuelwood collection. Monitoring frequency is semi-annual and "
    "requires at least ninety five percent survey coverage. "
) * 20

FOREST_CONTENT = (
    "Reforestation methodologies require demonstration of tree species "
    "survival rates above the project threshold, with ex ante estimation of "
    "carbon stock increments from allometric equations. The baseline scenario "
    "must be assessed against common practice land use in the project region. "
) * 12


async def _ingest_cookstove(service: KnowledgeBaseService) -> MethodologyDocument:
    return await service.ingest_document(
        registry="gold_standard",
        methodology_id="GS TPDD v3",
        title="Gold Standard TPDD v3",
        content=COOKSTOVE_CONTENT,
        version="v3",
        source_url="https://example.invalid/gs-tpdd-v3",
        metadata={"sector": "cookstoves"},
    )


@pytest.mark.asyncio
async def test_ingest_creates_chunks_and_deterministic_embeddings(db_session):
    service = KnowledgeBaseService(db_session)
    document = await _ingest_cookstove(service)

    result = await db_session.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
    )
    chunks = result.scalars().all()
    assert len(chunks) >= 3  # long content is split into overlapping windows
    assert [c.chunk_index for c in chunks] == sorted(c.chunk_index for c in chunks)
    assert all(c.embedding and len(c.embedding) == 256 for c in chunks)
    assert all(c.token_count > 0 for c in chunks)

    # Deterministic: same text embeds to the same vector.
    embedder = LocalHashEmbedder(dim=256)
    v1 = (await embedder.embed(["thermal efficiency cookstoves"]))[0]
    v2 = (await embedder.embed(["thermal efficiency cookstoves"]))[0]
    assert v1 == v2

    # Idempotent re-ingest of the same registry+methodology_id+version replaces.
    again = await _ingest_cookstove(service)
    assert again.id == document.id
    result = await db_session.execute(select(MethodologyDocument))
    assert len(result.scalars().all()) == 1
    result = await db_session.execute(select(KnowledgeChunk))
    assert len(result.scalars().all()) == len(chunks)


@pytest.mark.asyncio
async def test_top_k_pure_python_ranking():
    embedder = LocalHashEmbedder(dim=64)
    query = (await embedder.embed(["fuelwood thermal efficiency"]))[0]
    candidates = await embedder.embed([
        "completely unrelated financial accounting ledger entries",
        "fuelwood consumption and thermal efficiency of improved stoves",
    ])
    ranked = top_k(query, candidates, k=2)
    assert ranked[0][0] == 1
    assert ranked[0][1] > ranked[1][1]  # the on-topic candidate wins clearly
    assert ranked[0][1] > 0.3


@pytest.mark.asyncio
async def test_search_ranks_relevant_chunk_top(db_session):
    service = KnowledgeBaseService(db_session)
    await _ingest_cookstove(service)
    await service.ingest_document(
        registry="verra",
        methodology_id="VM0047",
        title="Verra Reforestation",
        content=FOREST_CONTENT,
        version="v1.0",
    )

    results = await service.search(
        "What thermal efficiency must improved cookstoves demonstrate?", k=5
    )
    assert results
    top = results[0]
    assert top["document"]["methodology_id"] == "GS TPDD v3"
    assert top["document"]["registry"] == "gold_standard"
    assert "thermal efficiency" in top["chunk"]["content"].lower()

    # Registry filter scopes results.
    verra_only = await service.search("tree species survival rates", registry="verra")
    assert verra_only and all(r["document"]["registry"] == "verra" for r in verra_only)


@pytest.mark.asyncio
async def test_query_knowledge_base_fallback_without_api_key(db_session, monkeypatch):
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    service = KnowledgeBaseService(db_session)
    await _ingest_cookstove(service)

    result = await service.query_knowledge_base(
        "What monitoring protocol applies to fuelwood consumption?"
    )
    assert result["unreviewed"] is True
    assert result["answer"] is None
    assert result["citations"] == []
    assert result["passages"], "fallback returns retrieved passages verbatim"
    assert result["passages"][0]["methodology_id"] == "GS TPDD v3"


@pytest.mark.asyncio
async def test_query_knowledge_base_rag_with_mocked_kimi(db_session, monkeypatch):
    service = KnowledgeBaseService(db_session)
    await _ingest_cookstove(service)

    class FakeKimi:
        async def reason(self, prompt, context, tools=None, response_schema=None):
            assert context.get("passages")
            assert response_schema is not None
            return {
                "answer": "Fuelwood consumption must follow the Kitchen Performance Test protocol.",
                "citations": ["GS TPDD v3"],
            }

    monkeypatch.setattr(
        "app.services.kimi_api.get_kimi_client", lambda: FakeKimi()
    )
    result = await service.query_knowledge_base(
        "What monitoring protocol applies to fuelwood consumption?"
    )
    assert result["unreviewed"] is False
    assert result["answer"] and "Kitchen Performance Test" in result["answer"]
    assert result["citations"] == ["GS TPDD v3"]


def test_knowledge_package_exposes_remediation_probe_names():
    # The remediation rule vvb_clarification → kb_draft_response probes
    # app.knowledge for query_knowledge_base / search_knowledge / query.
    assert callable(knowledge_pkg.query_knowledge_base)
    assert callable(knowledge_pkg.search_knowledge)


# ─── Knowledge API ───────────────────────────────────────────────────────────

DOCUMENT_PAYLOAD = {
    "registry": "ipcc",
    "methodology_id": "IPCC 2006 GL",
    "title": "IPCC 2006 Guidelines",
    "content": "Default emission factors for stationary combustion of biomass.",
    "version": "2006",
    "metadata": {"body": "ipcc"},
}


@pytest.mark.asyncio
async def test_knowledge_api_requires_auth(client):
    assert (await client.get("/api/v1/knowledge/documents")).status_code == 401
    assert (await client.post("/api/v1/knowledge/documents", json=DOCUMENT_PAYLOAD)).status_code == 401
    assert (await client.get("/api/v1/knowledge/search", params={"q": "emission"})).status_code == 401
    assert (
        await client.post("/api/v1/knowledge/query", json={"question": "what?"})
    ).status_code == 401


@pytest.mark.asyncio
async def test_knowledge_api_rejects_oversized_document(client, operator_headers):
    """Ingest bodies are capped (CWE-400): oversized content is rejected with 422."""
    payload = {**DOCUMENT_PAYLOAD, "content": "x" * 500_001}
    response = await client.post(
        "/api/v1/knowledge/documents", json=payload, headers=operator_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_knowledge_api_operator_write_and_delete_denied(client, operator_headers):
    # Operator can ingest (operator+ write), but deletion is admin-only.
    response = await client.post(
        "/api/v1/knowledge/documents", json=DOCUMENT_PAYLOAD, headers=operator_headers
    )
    assert response.status_code == 201
    doc_id = response.json()["id"]
    response = await client.delete(
        f"/api/v1/knowledge/documents/{doc_id}", headers=operator_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_knowledge_api_crud_admin(authenticated_client):
    ac, _user = authenticated_client
    response = await ac.post("/api/v1/knowledge/documents", json=DOCUMENT_PAYLOAD)
    assert response.status_code == 201
    doc_id = response.json()["id"]
    assert response.json()["chunk_count"] == 1

    # Admin can list (registry filter), fetch, search, and query.
    response = await ac.get("/api/v1/knowledge/documents")
    assert response.status_code == 200
    listed = response.json()["documents"]
    assert any(d["id"] == doc_id for d in listed)
    response = await ac.get("/api/v1/knowledge/documents", params={"registry": "ipcc"})
    assert all(d["registry"] == "ipcc" for d in response.json()["documents"])
    response = await ac.get("/api/v1/knowledge/documents", params={"registry": "verra"})
    assert response.json()["documents"] == []

    response = await ac.get(f"/api/v1/knowledge/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json()["chunks"][0]["content"]

    response = await ac.get("/api/v1/knowledge/search", params={"q": "emission factors combustion"})
    assert response.status_code == 200
    assert response.json()["results"][0]["document"]["id"] == doc_id

    response = await ac.post(
        "/api/v1/knowledge/query", json={"question": "What emission factors apply to biomass combustion?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["unreviewed"] is True  # no KIMI_API_KEY in tests
    assert body["passages"]

    response = await ac.delete(f"/api/v1/knowledge/documents/{doc_id}")
    assert response.status_code == 204
    response = await ac.get(f"/api/v1/knowledge/documents/{doc_id}")
    assert response.status_code == 404
    response = await ac.delete(f"/api/v1/knowledge/documents/{doc_id}")
    assert response.status_code == 404


# ─── Learning loop fixtures ──────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_project(db_session):
    email = f"learning-{uuid.uuid4().hex[:8]}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Learning Dev",
        role=UserRoleEnum.developer,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.commit()

    developer = Developer(id=uuid.uuid4(), user_id=user.id, company_name="Acme MRV")
    db_session.add(developer)
    await db_session.commit()

    project = Project(
        id=uuid.uuid4(),
        name="Learning Test Project",
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


async def _queue_item(db_session, project_id, agent_type="validation", priority=3):
    item = HumanReviewQueue(
        id=uuid.uuid4(),
        item_type=QueueItemTypeEnum.agent_review,
        item_id=uuid.uuid4(),
        reason=f"Review {agent_type} output",
        priority=priority,
        status=QueueStatusEnum.resolved,
        context_json={"project_id": str(project_id), "agent_type": agent_type},
        confidence_gap=0.05,
        human_decision="approve",
        resolution_notes="looks fine",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


async def _paired_decisions(db_session, project_id, item, confidence, human_action):
    await record_decision(
        db_session,
        project_id=project_id,
        agent_type="validation",
        action="queued_for_review",
        confidence_score=confidence,
        reasoning="agent routed to review",
        actor="agent:validation",
        review_queue_item_id=item.id,
    )
    await record_decision(
        db_session,
        project_id=project_id,
        agent_type="validation",
        action=human_action,
        reasoning=f"human {human_action}",
        actor="user:operator",
        review_queue_item_id=item.id,
    )


@pytest.mark.asyncio
async def test_compute_calibration_math(db_session, seeded_project):
    # Pair 1: approved at 0.90 (review bucket, not overridden).
    await _paired_decisions(
        db_session, seeded_project.id,
        await _queue_item(db_session, seeded_project.id), 0.90, "human_approved",
    )
    # Pair 2: rejected at 0.90 (review bucket, overridden).
    await _paired_decisions(
        db_session, seeded_project.id,
        await _queue_item(db_session, seeded_project.id), 0.90, "human_rejected",
    )
    # Pair 3: escalated at 0.97 (auto bucket, overridden).
    await _paired_decisions(
        db_session, seeded_project.id,
        await _queue_item(db_session, seeded_project.id), 0.97, "human_escalated",
    )
    # Pair 4: approved at 0.96 (auto bucket, not overridden).
    await _paired_decisions(
        db_session, seeded_project.id,
        await _queue_item(db_session, seeded_project.id), 0.96, "human_approved",
    )

    service = LearningLoopService(db_session)
    calibration = await service.compute_calibration(days=30)
    by_agent = {e["agent_type"]: e for e in calibration["agents"]}
    entry = by_agent["validation"]

    assert entry["n_paired_reviews"] == 4
    assert entry["n_overrides"] == 2
    assert entry["override_rate"] == 0.5
    assert entry["avg_confidence_when_overridden"] == round((0.90 + 0.97) / 2, 4)

    buckets = entry["accuracy_by_confidence_bucket"]
    assert buckets["0.85-0.95"]["n"] == 2
    assert buckets["0.85-0.95"]["overridden"] == 1
    assert buckets["0.85-0.95"]["accuracy"] == 0.5
    assert buckets[">=0.95"]["n"] == 2
    assert buckets[">=0.95"]["overridden"] == 1
    assert buckets[">=0.95"]["accuracy"] == 0.5


@pytest.mark.asyncio
async def test_suggested_threshold_and_clamp(db_session, seeded_project):
    service = LearningLoopService(db_session)

    # No history → no suggestion; effective threshold falls back to 0.95.
    assert await service.suggested_threshold("validation") is None
    assert await get_effective_threshold(db_session, "validation") == 0.95

    # An auto-advance later reversed by a human rejection raises the threshold.
    await record_decision(
        db_session,
        project_id=seeded_project.id,
        agent_type="validation",
        action="auto_advance",
        confidence_score=0.97,
        reasoning="auto advanced",
        actor="agent:validation",
    )
    await record_decision(
        db_session,
        project_id=seeded_project.id,
        agent_type="validation",
        action="human_rejected",
        reasoning="human reversed the auto-advance",
        actor="user:operator",
    )
    assert await service.suggested_threshold("validation") == 0.97
    assert await get_effective_threshold(db_session, "validation") == 0.97

    # Clamp: overridden auto-advance below the floor clamps up to 0.85.
    await record_decision(
        db_session,
        project_id=seeded_project.id,
        agent_type="calculation",
        action="auto_advance",
        confidence_score=0.50,
        reasoning="low-confidence auto advance",
        actor="agent:calculation",
    )
    await record_decision(
        db_session,
        project_id=seeded_project.id,
        agent_type="calculation",
        action="human_escalated",
        reasoning="human reversed",
        actor="user:operator",
    )
    assert await service.suggested_threshold("calculation") == 0.85

    # An auto-advance with no subsequent human reversal leaves the default.
    await record_decision(
        db_session,
        project_id=seeded_project.id,
        agent_type="reporting",
        action="auto_advance",
        confidence_score=0.99,
        reasoning="clean auto advance",
        actor="agent:reporting",
    )
    assert await service.suggested_threshold("reporting") is None


@pytest.mark.asyncio
async def test_orchestrator_advance_respects_raised_threshold(
    db_session, seeded_project, monkeypatch
):
    # Learned history: an ingestion auto-advance at 0.97 was reversed by a human.
    await record_decision(
        db_session,
        project_id=seeded_project.id,
        agent_type="ingestion",
        action="auto_advance",
        confidence_score=0.97,
        reasoning="previous auto advance later reversed",
        actor="agent:ingestion",
    )
    await record_decision(
        db_session,
        project_id=seeded_project.id,
        agent_type="ingestion",
        action="human_rejected",
        reasoning="human reversed the auto-advance",
        actor="user:operator",
    )

    class FakeAgent:
        def __init__(self, project_id, db_session=None):
            self.project_id = project_id

        async def execute(self, trigger_event, context):
            return AgentResult(
                status="completed",
                confidence_score=0.96,  # above default 0.95 but below learned 0.97
                output_data={"summary": "fake run"},
            )

    monkeypatch.setitem(orchestrator_module.AGENT_REGISTRY, "ingestion", FakeAgent)
    monkeypatch.setitem(orchestrator_module.AGENT_REGISTRY, "client_success", FakeAgent)

    orchestrator = KimiClawOrchestrator(db_session)
    result = await orchestrator.advance_project(seeded_project.id, max_steps=1)

    assert result["advanced"] is False
    assert result["reason"] == "insufficient_confidence"

    # The 0.96 dispatch queued a review item instead of auto-advancing.
    queue_result = await db_session.execute(select(HumanReviewQueue))
    items = queue_result.scalars().all()
    assert any(
        item.context_json.get("agent_type") == "ingestion" for item in items
    )
    decision_result = await db_session.execute(
        select(AgentDecision).where(AgentDecision.action == "queued_for_review")
    )
    assert any(d.agent_type == "ingestion" for d in decision_result.scalars().all())

    # Project did not transition.
    await db_session.refresh(seeded_project)
    assert seeded_project.status == ProjectStatusEnum.onboarding


@pytest.mark.asyncio
async def test_weekly_report_generation_and_persist(db_session, seeded_project):
    # Overridden auto-advance (drives the threshold suggestion) recorded first,
    # then the review pair with a resolution note.
    await record_decision(
        db_session,
        project_id=seeded_project.id,
        agent_type="validation",
        action="auto_advance",
        confidence_score=0.97,
        reasoning="auto advance later reversed",
        actor="agent:validation",
    )
    item = await _queue_item(db_session, seeded_project.id)
    await _paired_decisions(db_session, seeded_project.id, item, 0.97, "human_rejected")
    item.learning_feedback = {
        "human_decision": "human_rejected",
        "confidence_gap": 0.05,
        "agent_type": "validation",
        "resolution_notes": "baseline double-counted",
    }
    await db_session.commit()

    service = LearningLoopService(db_session)
    report = await service.weekly_retraining_report(persist=True)

    assert report["period_days"] == 7
    by_agent = {e["agent_type"]: e for e in report["agents"]}
    assert by_agent["validation"]["n_overrides"] == 1
    assert any("validation" in a for a in report["suggested_adjustments"])
    assert report["top_override_reasons"] == [
        {"reason": "baseline double-counted", "count": 1}
    ]
    assert "# Weekly Agent Retraining Brief" in report["markdown"]

    stored = await db_session.execute(select(LearningReport))
    rows = stored.scalars().all()
    assert len(rows) == 1
    assert rows[0].report_type == "weekly_retraining"
    assert rows[0].report["agents"]

    # record_override is an idempotent feedback consumer.
    feedback = await service.record_override(item)
    assert feedback["resolution_notes"] == "baseline double-counted"


@pytest.mark.asyncio
async def test_learning_api_requires_auth(client):
    assert (await client.get("/api/v1/learning/calibration")).status_code == 401
    assert (await client.get("/api/v1/learning/overrides")).status_code == 401
    assert (await client.post("/api/v1/learning/report/weekly/generate")).status_code == 401


@pytest.mark.asyncio
async def test_learning_api_operator(client, operator_headers, db_session, seeded_project):
    assert (await client.get("/api/v1/learning/report/weekly", headers=operator_headers)).status_code == 404

    item = await _queue_item(db_session, seeded_project.id)
    await _paired_decisions(db_session, seeded_project.id, item, 0.97, "human_rejected")

    response = await client.get(
        "/api/v1/learning/calibration", headers=operator_headers
    )
    assert response.status_code == 200
    assert any(e["agent_type"] == "validation" for e in response.json()["agents"])

    response = await client.post(
        "/api/v1/learning/report/weekly/generate", headers=operator_headers
    )
    assert response.status_code == 201

    response = await client.get("/api/v1/learning/report/weekly", headers=operator_headers)
    assert response.status_code == 200
    assert response.json()["report"]["agents"]

    response = await client.get("/api/v1/learning/overrides", headers=operator_headers)
    assert response.status_code == 200
    overrides = response.json()["overrides"]
    assert any(o["agent_type"] == "validation" for o in overrides)
    assert any(o["human_action"] == "human_rejected" for o in overrides)



# ─── Knowledge jobs (stub-safe, no network) ──────────────────────────────────

@pytest.mark.asyncio
async def test_check_methodology_updates_stub(db_session, patch_db_context):
    from app.tasks.knowledge_jobs import check_methodology_updates

    service = KnowledgeBaseService(db_session)
    document = await service.ingest_document(
        registry="verra",
        methodology_id="VM0048",
        title="Verra Methodology",
        content="Forest carbon stock monitoring methodology requirements.",
        version="v1.0",
    )
    fresh = check_methodology_updates()
    assert fresh["total_documents"] == 1
    assert fresh["due_for_refresh"] == 0
    assert "disabled" in fresh["fetching"]

    # Age the document past the 90-day refresh horizon.
    stale = datetime.now(UTC) - timedelta(days=120)
    await db_session.execute(
        update(MethodologyDocument)
        .where(MethodologyDocument.id == document.id)
        .values(updated_at=stale.replace(tzinfo=None))
    )
    await db_session.commit()
    aged = check_methodology_updates()
    assert aged["due_for_refresh"] == 1


@pytest.mark.asyncio
async def test_weekly_learning_report_task(db_session, patch_db_context):
    from app.tasks.learning_jobs import generate_weekly_learning_report

    summary = generate_weekly_learning_report()
    assert summary["generated_at"]
    assert summary["agent_count"] == 0  # fresh DB: no decisions in window

    stored = await db_session.execute(select(LearningReport))
    assert len(stored.scalars().all()) == 1
