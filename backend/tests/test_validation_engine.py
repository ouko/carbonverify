"""Tests for the Workflow Validation Engine."""

import hashlib
import json
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.encryption import compute_searchable_hash
from app.models import User, UserRoleEnum
from app.validation_engine.models import (
    EscalationLevel,
    EscalationStatus,
    HumanEscalation,
    RemediationAction,
    RemediationStatus,
    SyntheticActor,
    SyntheticActorType,
    ValidationProof,
    ValidationRemediation,
    ValidationRun,
    ValidationRunTransition,
    ValidationStepExecution,
    ValidationWorkflow,
    WorkflowRunStatus,
    WorkflowStepType,
)
from app.validation_engine.executors import DecisionGateExecutor, ServiceCallExecutor
from app.validation_engine.orchestrator import ValidationOrchestrator
from app.validation_engine.proofs import MerkleTree, ProofGenerator
from app.validation_engine.schemas import WorkflowGraph, WorkflowStep
from app.validation_engine.state_machine import TransitionError, WorkflowStateMachine
from app.validation_engine.synthetic import SyntheticActorFactory
from app.validation_engine.tasks import _recover_stuck_runs_async


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_workflow(db_session):
    """Create a simple test workflow."""
    graph = {
        "version": "1.0",
        "entry_step": "step_1",
        "steps": [
            {
                "id": "step_1",
                "name": "Test Step 1",
                "type": "http_request",
                "config": {
                    "method": "GET",
                    "url": "https://httpbin.org/get",
                    "timeout_ms": 5000,
                    "expected_status_codes": [200],
                },
                "next_on_success": ["step_2"],
                "next_on_failure": ["fail"],
            },
            {
                "id": "step_2",
                "name": "Test Step 2",
                "type": "wait",
                "config": {"duration_ms": 10},
                "next_on_success": ["end"],
                "next_on_failure": ["fail"],
            },
        ],
        "variables": {"test_var": "hello"},
    }
    canonical = json.dumps(graph, sort_keys=True, separators=(",", ":"))
    workflow = ValidationWorkflow(
        name="test_workflow",
        version="1.0.0",
        description="A test workflow",
        workflow_graph=graph,
        graph_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        active=True,
        sla_seconds=300,
        human_gates_required=False,
    )
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)
    return workflow


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user."""
    email = f"test-{uuid.uuid4().hex[:8]}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Test User",
        role=UserRoleEnum.admin,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ─── State Machine Tests ──────────────────────────────────────────────────────

class TestStateMachine:
    def test_valid_transition(self):
        sm = WorkflowStateMachine()
        result = sm.transition(WorkflowRunStatus.pending, WorkflowRunStatus.queued)
        assert result == WorkflowRunStatus.queued

    def test_invalid_transition_raises(self):
        sm = WorkflowStateMachine()
        with pytest.raises(TransitionError):
            sm.transition(WorkflowRunStatus.pending, WorkflowRunStatus.completed)

    def test_can_transition_returns_tuple(self):
        sm = WorkflowStateMachine()
        valid, error = sm.can_transition(
            WorkflowRunStatus.running, WorkflowRunStatus.step_validating
        )
        assert valid is True
        assert error is None

        valid, error = sm.can_transition(
            WorkflowRunStatus.completed, WorkflowRunStatus.running
        )
        assert valid is False
        assert error is not None

    def test_terminal_state(self):
        sm = WorkflowStateMachine()
        assert sm.is_terminal(WorkflowRunStatus.archived) is True
        # completed can transition to archived, so not terminal
        assert sm.is_terminal(WorkflowRunStatus.completed) is False
        assert sm.is_terminal(WorkflowRunStatus.running) is False

    def test_actor_permission_denied(self):
        sm = WorkflowStateMachine()
        valid, error = sm.can_transition(
            WorkflowRunStatus.pending, WorkflowRunStatus.running, actor_type="system"
        )
        assert valid is False
        assert "not allowed" in error

        valid, error = sm.can_transition(
            WorkflowRunStatus.pending, WorkflowRunStatus.running, actor_type="user"
        )
        assert valid is True


# ─── Merkle Tree Tests ────────────────────────────────────────────────────────

class TestMerkleTree:
    def test_single_leaf(self):
        leaves = ["abc123"]
        tree = MerkleTree(leaves)
        assert tree.get_root() == "abc123"

    def test_two_leaves(self):
        leaves = ["a", "b"]
        tree = MerkleTree(leaves)
        expected = hashlib.sha256(("a" + "b").encode()).hexdigest()
        assert tree.get_root() == expected

    def test_three_leaves(self):
        leaves = ["a", "b", "c"]
        tree = MerkleTree(leaves)
        # Left = hash(a+b), Right = hash(c+c)
        left = hashlib.sha256(("a" + "b").encode()).hexdigest()
        right = hashlib.sha256(("c" + "c").encode()).hexdigest()
        expected = hashlib.sha256((left + right).encode()).hexdigest()
        assert tree.get_root() == expected

    def test_proof_verification(self):
        leaves = ["leaf1", "leaf2", "leaf3", "leaf4"]
        tree = MerkleTree(leaves)
        for i, leaf in enumerate(leaves):
            path = tree.get_proof_path(i)
            assert tree.verify_leaf(leaf, i, path) is True
        # Wrong leaf should fail
        assert tree.verify_leaf("wrong", 0, tree.get_proof_path(0)) is False

    def test_empty_leaves_raises(self):
        with pytest.raises(ValueError):
            MerkleTree([])


# ─── Workflow Schema Tests ────────────────────────────────────────────────────

class TestWorkflowSchema:
    def test_valid_workflow_graph(self):
        graph = WorkflowGraph(
            entry_step="start",
            steps=[
                WorkflowStep(
                    id="start",
                    name="Start",
                    type=WorkflowStepType.http_request,
                    config={
                        "method": "GET",
                        "url": "https://example.com",
                        "timeout_ms": 5000,
                        "expected_status_codes": [200],
                    },
                    next_on_success=["end"],
                ),
            ],
        )
        assert graph.entry_step == "start"
        assert len(graph.steps) == 1

    def test_duplicate_step_ids_raises(self):
        with pytest.raises(ValueError):
            WorkflowGraph(
                entry_step="a",
                steps=[
                    WorkflowStep(id="a", name="A", type=WorkflowStepType.wait, config={"duration_ms": 10}),
                    WorkflowStep(id="a", name="B", type=WorkflowStepType.wait, config={"duration_ms": 10}),
                ],
            )

    def test_missing_entry_step_raises(self):
        with pytest.raises(ValueError):
            WorkflowGraph(
                entry_step="missing",
                steps=[
                    WorkflowStep(id="a", name="A", type=WorkflowStepType.wait, config={"duration_ms": 10}),
                ],
            )

    def test_invalid_next_reference_raises(self):
        with pytest.raises(ValueError):
            WorkflowGraph(
                entry_step="a",
                steps=[
                    WorkflowStep(
                        id="a",
                        name="A",
                        type=WorkflowStepType.wait,
                        config={"duration_ms": 10},
                        next_on_success=["nonexistent"],
                    ),
                ],
            )


# ─── Synthetic Actor Tests ────────────────────────────────────────────────────

class TestSyntheticActorFactory:
    @pytest.mark.asyncio
    async def test_create_actor(self, db_session):
        factory = SyntheticActorFactory()
        actor = await factory.create_actor(
            db_session,
            name="test_actor",
            actor_type=SyntheticActorType.user,
            profile_key="impatient_mobile_user",
        )
        assert actor.name == "test_actor"
        assert actor.actor_type == SyntheticActorType.user
        assert actor.profile_key == "impatient_mobile_user"
        assert "synthetic_actor_id" in actor.markers
        assert actor.active is True
        assert actor.usage_count == 0

    @pytest.mark.asyncio
    async def test_get_actor(self, db_session):
        factory = SyntheticActorFactory()
        actor = await factory.create_actor(
            db_session,
            name="cached_actor",
            actor_type=SyntheticActorType.service,
        )
        fetched = await factory.get_actor(db_session, str(actor.id))
        assert fetched is not None
        assert fetched.id == actor.id

    @pytest.mark.asyncio
    async def test_mark_used(self, db_session):
        factory = SyntheticActorFactory()
        actor = await factory.create_actor(
            db_session,
            name="used_actor",
            actor_type=SyntheticActorType.browser,
        )
        await factory.mark_actor_used(db_session, actor)
        assert actor.usage_count == 1
        assert actor.last_used_at is not None


# ─── Orchestrator Tests ───────────────────────────────────────────────────────

class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_create_run(self, db_session, test_workflow, test_user):
        orchestrator = ValidationOrchestrator(db_session)
        run = await orchestrator.create_run(
            workflow_id=str(test_workflow.id),
            trigger_event="manual_test",
            input_data={"test": True},
            project_id=None,
            triggered_by=str(test_user.id),
        )
        assert run.status == WorkflowRunStatus.pending
        assert run.trigger_event == "manual_test"
        assert run.input_data == {"test": True}

    @pytest.mark.asyncio
    async def test_advance_state(self, db_session, test_workflow, test_user):
        orchestrator = ValidationOrchestrator(db_session)
        run = await orchestrator.create_run(
            workflow_id=str(test_workflow.id),
            trigger_event="manual_test",
            input_data={},
            triggered_by=str(test_user.id),
        )
        transition = await orchestrator.advance_state(
            run, WorkflowRunStatus.queued, reason="Test advance"
        )
        assert run.status == WorkflowRunStatus.queued
        assert transition.from_state == "pending"
        assert transition.to_state == "queued"
        assert transition.transition_hash is not None

    @pytest.mark.asyncio
    async def test_advance_state_chain_integrity(self, db_session, test_workflow, test_user):
        orchestrator = ValidationOrchestrator(db_session)
        run = await orchestrator.create_run(
            workflow_id=str(test_workflow.id),
            trigger_event="manual_test",
            input_data={},
            triggered_by=str(test_user.id),
        )
        t1 = await orchestrator.advance_state(run, WorkflowRunStatus.queued)
        t2 = await orchestrator.advance_state(run, WorkflowRunStatus.running)
        assert t2.previous_hash == t1.transition_hash

    @pytest.mark.asyncio
    async def test_invalid_advance_raises(self, db_session, test_workflow, test_user):
        orchestrator = ValidationOrchestrator(db_session)
        run = await orchestrator.create_run(
            workflow_id=str(test_workflow.id),
            trigger_event="manual_test",
            input_data={},
            triggered_by=str(test_user.id),
        )
        with pytest.raises(TransitionError):
            await orchestrator.advance_state(run, WorkflowRunStatus.completed)


# ─── API Tests ────────────────────────────────────────────────────────────────

class TestValidationEngineAPI:
    @pytest.mark.asyncio
    async def test_create_workflow(self, authenticated_client):
        client, user = authenticated_client
        payload = {
            "name": "api_test_workflow",
            "version": "1.0.0",
            "description": "Created via API",
            "workflow_graph": {
                "entry_step": "start",
                "steps": [
                    {
                        "id": "start",
                        "name": "Start",
                        "type": "wait",
                        "config": {"duration_ms": 100},
                        "next_on_success": ["end"],
                    }
                ],
                "variables": {},
            },
            "sla_seconds": 300,
            "human_gates_required": False,
        }
        response = await client.post("/validation/workflows", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "api_test_workflow"
        assert data["graph_hash"] is not None

    @pytest.mark.asyncio
    async def test_list_workflows(self, authenticated_client):
        client, user = authenticated_client
        response = await client.get("/validation/workflows")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_workflow(self, authenticated_client):
        client, user = authenticated_client
        # Create first
        payload = {
            "name": "get_test",
            "version": "1.0.0",
            "workflow_graph": {
                "entry_step": "start",
                "steps": [
                    {
                        "id": "start",
                        "name": "Start",
                        "type": "wait",
                        "config": {"duration_ms": 100},
                        "next_on_success": ["end"],
                    }
                ],
                "variables": {},
            },
        }
        create_resp = await client.post("/validation/workflows", json=payload)
        wf_id = create_resp.json()["id"]

        response = await client.get(f"/validation/workflows/{wf_id}")
        assert response.status_code == 200
        assert response.json()["id"] == wf_id

    @pytest.mark.asyncio
    async def test_trigger_run(self, authenticated_client):
        client, user = authenticated_client
        # Create workflow
        payload = {
            "name": "run_test_workflow",
            "version": "1.0.0",
            "workflow_graph": {
                "entry_step": "start",
                "steps": [
                    {
                        "id": "start",
                        "name": "Start",
                        "type": "wait",
                        "config": {"duration_ms": 100},
                        "next_on_success": ["end"],
                    }
                ],
                "variables": {},
            },
        }
        wf_resp = await client.post("/validation/workflows", json=payload)
        wf_id = wf_resp.json()["id"]

        # Trigger run
        run_payload = {
            "workflow_id": wf_id,
            "trigger_event": "api_test",
            "input_data": {"foo": "bar"},
        }
        response = await client.post("/validation/runs", json=run_payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["workflow_id"] == wf_id

    @pytest.mark.asyncio
    async def test_create_synthetic_actor(self, authenticated_client):
        client, user = authenticated_client
        payload = {
            "name": "api_test_actor",
            "actor_type": "user",
            "profile_key": "impatient_mobile_user",
            "markers": {"custom": True},
            "behavior_config": {},
            "context_data": {},
        }
        response = await client.post("/validation/synthetic-actors", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "api_test_actor"
        assert data["actor_type"] == "user"

    @pytest.mark.asyncio
    async def test_list_synthetic_actors(self, authenticated_client):
        client, user = authenticated_client
        response = await client.get("/validation/synthetic-actors")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_cancel_run(self, authenticated_client, db_session):
        client, user = authenticated_client
        # Create workflow and run
        payload = {
            "name": "cancel_test",
            "version": "1.0.0",
            "workflow_graph": {
                "entry_step": "start",
                "steps": [
                    {
                        "id": "start",
                        "name": "Start",
                        "type": "wait",
                        "config": {"duration_ms": 100},
                        "next_on_success": ["end"],
                    }
                ],
                "variables": {},
            },
        }
        wf_resp = await client.post("/validation/workflows", json=payload)
        wf_id = wf_resp.json()["id"]

        run_payload = {
            "workflow_id": wf_id,
            "trigger_event": "cancel_test",
            "input_data": {},
        }
        run_resp = await client.post("/validation/runs", json=run_payload)
        run_id = run_resp.json()["id"]

        response = await client.post(f"/validation/runs/{run_id}/cancel")
        assert response.status_code == 200
        assert response.json()["detail"] == "Run cancelled"


# ─── Proof Certificate Tests ──────────────────────────────────────────────────

class TestProofCertificate:
    @pytest.mark.asyncio
    async def test_generate_certificate(self, db_session, test_workflow, test_user):
        orchestrator = ValidationOrchestrator(db_session)
        run = await orchestrator.create_run(
            workflow_id=str(test_workflow.id),
            trigger_event="cert_test",
            input_data={},
            triggered_by=str(test_user.id),
        )
        run.started_at = datetime.now(timezone.utc)
        run.completed_at = datetime.now(timezone.utc)
        run.merkle_root = "abc123" * 8  # 48 chars
        run.radix_tx_ref = "tx_ref_123"
        await db_session.commit()

        # Create some proofs
        for i in range(3):
            proof = ValidationProof(
                run_id=run.id,
                step_execution_id=None,
                proof_type="http_request",
                proof_data={"index": i},
                proof_hash=hashlib.sha256(str(i).encode()).hexdigest(),
                merkle_leaf_index=i,
            )
            db_session.add(proof)
        await db_session.commit()

        result = await db_session.execute(
            select(ValidationProof).where(ValidationProof.run_id == run.id)
        )
        proofs = list(result.scalars().all())

        generator = ProofGenerator()
        cert = generator.generate_certificate(run, proofs)

        assert cert["run_id"] == str(run.id)
        assert cert["merkle_root"] == run.merkle_root
        assert cert["radix_tx_ref"] == run.radix_tx_ref
        assert cert["step_count"] == 3
        assert cert["certificate_hash"] is not None
        assert len(cert["step_hashes"]) == 3


# ─── Remediation Tests ────────────────────────────────────────────────────────

class TestRemediation:
    @pytest.mark.asyncio
    async def test_remediation_creation(self, db_session, test_workflow, test_user):
        run = ValidationRun(
            workflow_id=test_workflow.id,
            trigger_event="remediation_test",
            input_data={},
            status=WorkflowRunStatus.running,
            triggered_by=test_user.id,
        )
        db_session.add(run)
        await db_session.commit()

        remediation = ValidationRemediation(
            run_id=run.id,
            failure_condition="Connection timeout",
            action=RemediationAction.retry,
            status=RemediationStatus.attempted,
        )
        db_session.add(remediation)
        await db_session.commit()

        result = await db_session.execute(
            select(ValidationRemediation).where(ValidationRemediation.run_id == run.id)
        )
        fetched = result.scalar_one()
        assert fetched.action == RemediationAction.retry
        assert fetched.status == RemediationStatus.attempted


# ─── Human Escalation Tests ───────────────────────────────────────────────────

class TestHumanEscalation:
    @pytest.mark.asyncio
    async def test_escalation_creation(self, db_session, test_workflow, test_user):
        run = ValidationRun(
            workflow_id=test_workflow.id,
            trigger_event="escalation_test",
            input_data={},
            status=WorkflowRunStatus.failed,
            triggered_by=test_user.id,
        )
        db_session.add(run)
        await db_session.commit()

        escalation = HumanEscalation(
            run_id=run.id,
            escalation_reason="Critical failure in step validation",
            severity_score=0.9,
            level=EscalationLevel.l3_architect,
            status=EscalationStatus.pending,
            sla_deadline=datetime.now(timezone.utc),
        )
        db_session.add(escalation)
        await db_session.commit()

        result = await db_session.execute(
            select(HumanEscalation).where(HumanEscalation.run_id == run.id)
        )
        fetched = result.scalar_one()
        assert fetched.level == EscalationLevel.l3_architect
        assert fetched.status == EscalationStatus.pending
        assert fetched.severity_score == 0.9

    @pytest.mark.asyncio
    async def test_escalation_resolution(self, db_session, test_workflow, test_user):
        run = ValidationRun(
            workflow_id=test_workflow.id,
            trigger_event="escalation_resolve_test",
            input_data={},
            status=WorkflowRunStatus.failed,
            triggered_by=test_user.id,
        )
        db_session.add(run)
        await db_session.commit()

        escalation = HumanEscalation(
            run_id=run.id,
            escalation_reason="Test",
            severity_score=0.5,
            level=EscalationLevel.l1_operator,
            status=EscalationStatus.pending,
        )
        db_session.add(escalation)
        await db_session.commit()

        escalation.status = EscalationStatus.resolved
        escalation.human_decision = "approve"
        escalation.human_notes = "All good"
        escalation.resolved_at = datetime.now(timezone.utc)
        await db_session.commit()

        result = await db_session.execute(
            select(HumanEscalation).where(HumanEscalation.id == escalation.id)
        )
        fetched = result.scalar_one()
        assert fetched.status == EscalationStatus.resolved
        assert fetched.human_decision == "approve"


# ─── Safe Evaluator Tests ─────────────────────────────────────────────────────

class TestSafeEvaluator:
    def test_simple_comparisons(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("5 > 3", {}) is True
        assert executor._evaluate_condition("5 < 3", {}) is False
        assert executor._evaluate_condition("5 == 5", {}) is True
        assert executor._evaluate_condition("5 != 3", {}) is True
        assert executor._evaluate_condition("5 >= 5", {}) is True
        assert executor._evaluate_condition("5 <= 4", {}) is False

    def test_string_equality(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("'hello' == 'hello'", {}) is True
        assert executor._evaluate_condition("'hello' != 'world'", {}) is True

    def test_arithmetic(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("2 + 2 == 4", {}) is True
        assert executor._evaluate_condition("10 - 3 == 7", {}) is True
        assert executor._evaluate_condition("3 * 4 == 12", {}) is True
        assert executor._evaluate_condition("10 / 2 == 5.0", {}) is True

    def test_boolean_logic(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("True and True", {}) is True
        assert executor._evaluate_condition("True and False", {}) is False
        assert executor._evaluate_condition("True or False", {}) is True
        assert executor._evaluate_condition("not False", {}) is True
        assert executor._evaluate_condition("not True", {}) is False

    def test_in_operator(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("'a' in ['a', 'b']", {}) is True
        assert executor._evaluate_condition("'c' in ['a', 'b']", {}) is False

    def test_len_function(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("len([1, 2, 3]) == 3", {}) is True
        assert executor._evaluate_condition("len('hello') == 5", {}) is True

    def test_variable_interpolation(self):
        executor = DecisionGateExecutor()
        context = {"variables": {"score": 85, "name": "test"}}
        assert executor._evaluate_condition("${score} > 80", context) is True
        assert executor._evaluate_condition("${name} == 'test'", context) is True

    def test_none_literal(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("None == None", {}) is True

    def test_disallowed_import(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("__import__('os')", {}) is False

    def test_disallowed_name(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("open('file.txt')", {}) is False

    def test_disallowed_attribute_access(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("(1).__class__", {}) is False

    def test_disallowed_call(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("exec('pass')", {}) is False

    def test_malformed_expression(self):
        executor = DecisionGateExecutor()
        assert executor._evaluate_condition("5 > > 3", {}) is False


# ─── ServiceCallExecutor Tests ────────────────────────────────────────────────

class TestServiceCallExecutor:
    @pytest.mark.asyncio
    async def test_service_call_re_raises_exception(self):
        executor = ServiceCallExecutor()

        class FakeService:
            def broken_method(self):
                raise ValueError("Intentional failure")

        ServiceCallExecutor.register_service("fake", FakeService())

        config = {
            "service_name": "fake",
            "method_name": "broken_method",
            "args": [],
            "kwargs": {},
        }

        with pytest.raises(RuntimeError, match="Service call 'fake.broken_method' failed"):
            await executor.execute(config, {}, None)


# ─── Escalation Resolution Tests ──────────────────────────────────────────────

class TestEscalationResolution:
    @pytest.mark.asyncio
    async def test_resolve_escalation_transitions_failed_run(self, authenticated_client, db_session, test_workflow, test_user):
        client, user = authenticated_client
        # Create a run in failed state awaiting human decision
        run = ValidationRun(
            workflow_id=test_workflow.id,
            trigger_event="escalation_resolve_api_test",
            input_data={},
            status=WorkflowRunStatus.failed,
            triggered_by=test_user.id,
            awaiting_human_decision=True,
        )
        db_session.add(run)
        await db_session.commit()

        escalation = HumanEscalation(
            run_id=run.id,
            escalation_reason="Test resolution",
            severity_score=0.5,
            level=EscalationLevel.l1_operator,
            status=EscalationStatus.pending,
        )
        db_session.add(escalation)
        await db_session.commit()

        response = await client.post(
            f"/validation/escalations/{escalation.id}/resolve",
            json={"decision": "approve", "notes": "Looks good"},
        )
        assert response.status_code == 200
        assert response.json()["detail"] == "Escalation resolved"

        # Refresh run and verify status transitioned to queued
        await db_session.refresh(run)
        assert run.status == WorkflowRunStatus.queued
        assert run.awaiting_human_decision is False


# ─── Run Failure SLA Tests ────────────────────────────────────────────────────

class TestRunFailureSLA:
    @pytest.mark.asyncio
    async def test_sla_deadline_extended_on_failure(self, db_session, test_workflow, test_user):
        from datetime import timedelta
        orchestrator = ValidationOrchestrator(db_session)
        run = await orchestrator.create_run(
            workflow_id=str(test_workflow.id),
            trigger_event="sla_test",
            input_data={},
            triggered_by=str(test_user.id),
        )
        # Force run into running state so _handle_run_failure can be called
        run.status = WorkflowRunStatus.running
        await db_session.commit()

        await orchestrator._handle_run_failure(run, "Test failure")

        result = await db_session.execute(
            select(HumanEscalation).where(HumanEscalation.run_id == run.id)
        )
        escalation = result.scalar_one()
        assert escalation.sla_deadline is not None
        # SQLite returns offset-naive datetimes; compare without tz info
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Should be at least 3 hours and 55 minutes in the future
        assert (escalation.sla_deadline - now) > timedelta(hours=3, minutes=55)


# ─── Stuck Run Recovery Tests ─────────────────────────────────────────────────

class TestStuckRunRecovery:
    @pytest.mark.asyncio
    async def test_recover_stuck_runs(self, db_session, test_workflow, test_user):
        from datetime import timedelta
        # Create a run that appears stuck (updated_at > 2 hours ago)
        run = ValidationRun(
            workflow_id=test_workflow.id,
            trigger_event="stuck_test",
            input_data={},
            status=WorkflowRunStatus.running,
            triggered_by=test_user.id,
        )
        db_session.add(run)
        await db_session.commit()

        # Manually back-date updated_at to simulate a stuck run
        run.updated_at = datetime.now(timezone.utc) - timedelta(hours=3)
        await db_session.commit()

        result = await _recover_stuck_runs_async(db=db_session)
        assert result["recovered_count"] >= 1

        # Re-fetch run after commit in recovery task detached it
        run_result = await db_session.execute(
            select(ValidationRun).where(ValidationRun.id == run.id)
        )
        run = run_result.scalar_one()
        assert run.status == WorkflowRunStatus.failed

        escalation_result = await db_session.execute(
            select(HumanEscalation).where(HumanEscalation.run_id == run.id)
        )
        escalation = escalation_result.scalar_one()
        assert escalation.escalation_reason == "Stuck run detected by recovery task"
        assert escalation.status == EscalationStatus.pending

    @pytest.mark.asyncio
    async def test_recover_stuck_runs_ignores_recent_runs(self, db_session, test_workflow, test_user):
        run = ValidationRun(
            workflow_id=test_workflow.id,
            trigger_event="not_stuck_test",
            input_data={},
            status=WorkflowRunStatus.running,
            triggered_by=test_user.id,
        )
        db_session.add(run)
        await db_session.commit()

        result = await _recover_stuck_runs_async(db=db_session)
        assert result["recovered_count"] == 0

        # Re-fetch run after commit in recovery task detached it
        run_result = await db_session.execute(
            select(ValidationRun).where(ValidationRun.id == run.id)
        )
        run = run_result.scalar_one()
        assert run.status == WorkflowRunStatus.running
