"""Tests for the immutable agent decision audit trail (Merkle chain + API)."""

import uuid

import pytest
from sqlalchemy import select, update

from app.models import AgentDecision
from app.orchestrator.audit_chain import (
    compute_record_hash,
    hash_fields_for,
    record_decision,
    verify_chain,
)


async def _record(db, **overrides):
    kwargs = {
        "agent_type": "ingestion",
        "action": "auto_advance",
        "reasoning": "All checks passed with high confidence.",
        "actor": "agent:ingestion",
        "confidence_score": 0.97,
        "input_summary": {"agent_run_id": str(uuid.uuid4())},
    }
    kwargs.update(overrides)
    return await record_decision(db, **kwargs)


async def _all_decisions(db):
    result = await db.execute(select(AgentDecision).order_by(AgentDecision.created_at.asc()))
    return result.scalars().all()


@pytest.mark.asyncio
async def test_record_decision_chains_hashes(db_session):
    first = await _record(db_session)
    second = await _record(db_session)
    third = await _record(db_session, agent_type="validation", action="queued_for_review")

    assert first.prev_hash is None
    assert first.record_hash and len(first.record_hash) == 64
    assert second.prev_hash == first.record_hash
    assert third.prev_hash == second.record_hash


@pytest.mark.asyncio
async def test_verify_chain_passes(db_session):
    for _ in range(3):
        await _record(db_session)

    result = await verify_chain(db_session)
    assert result["valid"] is True
    assert result["checked"] == 3
    assert result["first_broken_id"] is None


@pytest.mark.asyncio
async def test_tampering_a_row_breaks_chain(db_session):
    first = await _record(db_session)
    await _record(db_session)
    await _record(db_session)

    # Tamper: mutate a hashed field without re-hashing.
    await db_session.execute(
        update(AgentDecision)
        .where(AgentDecision.id == first.id)
        .values(reasoning="tampered reasoning")
    )
    await db_session.commit()

    result = await verify_chain(db_session)
    assert result["valid"] is False
    assert result["checked"] == 3
    assert result["first_broken_id"] == first.decision_id


@pytest.mark.asyncio
async def test_reordering_breaks_chain(db_session):
    await _record(db_session)
    second = await _record(db_session)

    # Swap the chain: make the second record point at nothing and re-hash it.
    second.prev_hash = None
    second.record_hash = compute_record_hash(hash_fields_for(second))
    await db_session.commit()

    result = await verify_chain(db_session)
    assert result["valid"] is False


@pytest.mark.asyncio
async def test_get_decision_authenticated(authenticated_client, db_session):
    ac, _user = authenticated_client
    decision = await _record(db_session, reasoning="explainable test reasoning")

    response = await ac.get(f"/api/v1/audit/{decision.decision_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["decision_id"] == str(decision.decision_id)
    assert data["reasoning"] == "explainable test reasoning"
    assert data["action"] == "auto_advance"
    assert data["actor"] == "agent:ingestion"
    assert data["record_hash"] == decision.record_hash


@pytest.mark.asyncio
async def test_get_decision_unauthenticated(client, db_session):
    decision = await _record(db_session)
    response = await client.get(f"/api/v1/audit/{decision.decision_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_decision_not_found(authenticated_client, db_session):
    ac, _user = authenticated_client
    response = await ac.get(f"/api/v1/audit/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_decisions_filters(authenticated_client, db_session):
    ac, _user = authenticated_client
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()
    await _record(db_session, project_id=project_a, agent_type="ingestion", action="auto_advance")
    await _record(db_session, project_id=project_a, agent_type="validation", action="escalated")
    await _record(db_session, project_id=project_b, agent_type="reporting", action="queued_for_review")

    # No filter: all three.
    response = await ac.get("/api/v1/audit/decisions")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["decisions"]) == 3

    # Filter by project_id.
    response = await ac.get("/api/v1/audit/decisions", params={"project_id": str(project_a)})
    body = response.json()
    assert body["total"] == 2
    assert all(d["project_id"] == str(project_a) for d in body["decisions"])

    # Filter by agent_type.
    response = await ac.get("/api/v1/audit/decisions", params={"agent_type": "reporting"})
    body = response.json()
    assert body["total"] == 1
    assert body["decisions"][0]["action"] == "queued_for_review"

    # Combined filter.
    response = await ac.get(
        "/api/v1/audit/decisions",
        params={"project_id": str(project_a), "action": "escalated"},
    )
    body = response.json()
    assert body["total"] == 1
    assert body["decisions"][0]["agent_type"] == "validation"


@pytest.mark.asyncio
async def test_verify_chain_endpoint(authenticated_client, db_session):
    ac, _user = authenticated_client
    await _record(db_session)
    await _record(db_session)

    response = await ac.post("/api/v1/audit/verify-chain")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["checked"] == 2


@pytest.mark.asyncio
async def test_verify_chain_endpoint_detects_tamper(authenticated_client, db_session):
    ac, _user = authenticated_client
    await _record(db_session)
    target = await _record(db_session)

    await db_session.execute(
        update(AgentDecision)
        .where(AgentDecision.id == target.id)
        .values(confidence_score=0.11)
    )
    await db_session.commit()

    response = await ac.post("/api/v1/audit/verify-chain")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["checked"] == 2
    assert body["first_broken_id"] == str(target.decision_id)


@pytest.mark.asyncio
async def test_human_decision_recorded_with_actor(db_session):
    decision = await _record(
        db_session,
        action="human_approved",
        actor="user@carbonverify.io",
        confidence_score=None,
        review_queue_item_id=uuid.uuid4(),
    )
    assert decision.actor == "user@carbonverify.io"
    result = await verify_chain(db_session)
    assert result["valid"] is True
