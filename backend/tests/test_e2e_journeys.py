"""End-to-end API journeys with REAL authentication.

Unlike the rest of the suite (which overrides ``get_current_user`` with a
dependency stub), every journey here obtains a genuine JWT by posting to
``POST /auth/login`` and then sends ``Authorization: Bearer <token>`` on all
subsequent calls. This exercises the full auth middleware stack — bearer
parsing, JWT decode, user lookup, role checking – exactly as production does.

Journeys covered:

1. Operator morning round: login → triage escalations (list/stats/health
   score) → review audit decisions → review queue → acknowledge + resolve one
   escalation → verify both actions landed in the Merkle-chained decision
   audit trail.
2. Project onboarding over HTTP: developer login is rejected from
   project creation (RBAC reality: creation is operator-gated) and an
   operator completes create project → data source → CSV upload (multipart,
   real processing pipeline via inline Celery eager execution) → calculation
   → calculation retrieval → report list.
3. VVB clarification loop: submitted project + report with an outstanding
   VVB query → dispatch the REAL ``vvb_liaison`` agent over HTTP → drafted
   response recorded as an ``AgentDecision`` retrievable via
   ``GET /api/v1/audit/{decision_id}`` and verifiable via the chain endpoint.
4. Auth negatives: every new ``/api/v1`` prefix returns 401 without a token;
   viewer role gets 403 on operator-only writes.
5. Regression tripwire: reflects over ``app.routes`` and asserts every route
   under the new prefixes carries an auth dependency, so a future endpoint
   added without auth fails loudly here.
"""

import uuid
from datetime import date

import boto3
import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.clamav_scanner as clamav_module
import app.services.s3 as s3_module
from app.auth.dependencies import PermissionChecker, RoleChecker
from app.auth.security import get_password_hash
from app.core.encryption import compute_searchable_hash
from app.escalations.models import EscalationEvent, EscalationStatus
from app.main import app
from app.models import (
    CalculationRun,
    DataSource,
    Developer,
    HumanReviewQueue,
    MethodologyEnum,
    Project,
    ProjectStatusEnum,
    QueueItemTypeEnum,
    QueueStatusEnum,
    Report,
    ReportStatusEnum,
    ReportTemplateTypeEnum,
    User,
    UserRoleEnum,
)
TEST_PASSWORD = "E2eTestPass123!"


# ─── Hermetic session store ───────────────────────────────────────────────────


class _FakeRedis:
    """In-memory double for ``redis.asyncio.Redis`` covering the
    ``SessionManager`` surface (strings, sets, pipelines, scans)."""

    def __init__(self):
        self._strings: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}

    async def setex(self, key, ttl, value):
        self._strings[key] = value
        return True

    async def get(self, key):
        return self._strings.get(key)

    async def delete(self, *keys):
        removed = 0
        for key in keys:
            removed += int(self._strings.pop(key, None) is not None)
            self._sets.pop(key, None)
        return removed

    async def exists(self, key):
        return int(key in self._strings)

    async def sadd(self, key, *members):
        self._sets.setdefault(key, set()).update(members)
        return len(members)

    async def srem(self, key, *members):
        target = self._sets.get(key, set())
        before = len(target)
        for member in members:
            target.discard(member)
        return before - len(target)

    async def smembers(self, key):
        return set(self._sets.get(key, set()))

    async def scan_iter(self, match=None):
        prefix = (match or "*").rstrip("*")
        for key in list(self._strings):
            if key.startswith(prefix):
                yield key

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, client: _FakeRedis):
        self._client = client
        self._ops: list[tuple] = []

    def setex(self, key, ttl, value):
        self._ops.append(("setex", key, ttl, value))
        return self

    def sadd(self, key, *members):
        self._ops.append(("sadd", key, *members))
        return self

    async def execute(self):
        results = [
            await getattr(self._client, op[0])(*op[1:]) for op in self._ops
        ]
        self._ops = []
        return results


@pytest.fixture(autouse=True)
def _hermetic_session_store(monkeypatch):
    """Route ``SessionManager``'s Redis client to an in-memory double.

    conftest points ``REDIS_URL`` at ``localhost:6379``, so ``POST /auth/login``
    writes sessions to a REAL shared Redis. Any other process using that Redis
    (a parallel dev stack, another test run, a FLUSHALL) can fail the session
    write and 500 the login call — which made these journeys fail once under a
    loaded coverage run while passing in isolation. Keeping the session store
    in memory removes the external dependency.
    """
    from app.auth import sessions as sessions_module

    fake = _FakeRedis()
    monkeypatch.setattr(sessions_module, "_get_redis", lambda: fake)


# ─── Helpers ──────────────────────────────────────────────────────────────────


async def _seed_user(
    db: AsyncSession, role: UserRoleEnum, suffix: str | None = None
) -> User:
    """Create a user with a real bcrypt password so /auth/login works."""
    suffix = suffix or uuid.uuid4().hex[:8]
    email = f"e2e-{role.value}-{suffix}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name=f"E2E {role.value}",
        role=role,
        mfa_enabled=False,
        hashed_password=get_password_hash(TEST_PASSWORD),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client: AsyncClient, email: str) -> str:
    """Obtain a genuine access token through the real login endpoint."""
    response = await client.post(
        "/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    return data["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_developer(db: AsyncSession) -> Developer:
    user = await _seed_user(db, UserRoleEnum.developer)
    developer = Developer(id=uuid.uuid4(), user_id=user.id, company_name="E2E MRV Ltd")
    db.add(developer)
    await db.commit()
    await db.refresh(developer)
    return developer


# ─── 1. Operator morning round ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_operator_morning_round(client: AsyncClient, db_session: AsyncSession):
    """Login → triage escalations → ack + resolve → audit trail proves both."""
    operator = await _seed_user(db_session, UserRoleEnum.operator)

    # Seed the morning backlog directly: two open escalations + a review item.
    e1 = EscalationEvent(
        id=uuid.uuid4(),
        source="agent:validation",
        title="Duplicate baseline upload",
        detail="Two uploads share a SHA-256 hash.",
        context_package={"evidence": {"upload_count": 2}},
        priority=1,
        severity_score=0.8,
        status=EscalationStatus.open,
        channels_sent={},
    )
    e2 = EscalationEvent(
        id=uuid.uuid4(),
        source="system:remediation",
        title="Calculation agent stalled",
        detail="No state advance in 48h.",
        context_package={},
        priority=2,
        severity_score=0.5,
        status=EscalationStatus.open,
        channels_sent={},
    )
    review_item = HumanReviewQueue(
        id=uuid.uuid4(),
        item_type=QueueItemTypeEnum.data_anomaly,
        item_id=uuid.uuid4(),
        reason="Confidence below threshold",
        priority=3,
        status=QueueStatusEnum.pending,
    )
    db_session.add_all([e1, e2, review_item])
    await db_session.commit()

    token = await _login(client, operator.email)

    # Triage views.
    resp = await client.get("/api/v1/escalations/", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {str(e1.id), str(e2.id)}

    resp = await client.get("/api/v1/escalations/stats", headers=_auth(token))
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total"] == 2
    assert stats["by_status"]["open"] == 2
    assert stats["open_p0"] == 0

    resp = await client.get("/api/v1/escalations/health/score", headers=_auth(token))
    assert resp.status_code == 200
    score = resp.json()
    assert 0 <= score["score"] <= 100
    assert "open_escalations" in score["components"]

    resp = await client.get("/api/v1/audit/decisions", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0  # nothing decided yet today

    resp = await client.get("/review-queue/", headers=_auth(token))
    assert resp.status_code == 200
    assert any(item["id"] == str(review_item.id) for item in resp.json())

    # Work the P1 escalation: acknowledge, then resolve with notes.
    resp = await client.post(
        f"/api/v1/escalations/{e1.id}/acknowledge", headers=_auth(token)
    )
    assert resp.status_code == 200
    acked = resp.json()
    assert acked["status"] == "acknowledged"
    assert acked["acknowledged_by"] == str(operator.id)
    assert acked["acknowledged_at"] is not None

    resp = await client.post(
        f"/api/v1/escalations/{e1.id}/resolve",
        headers=_auth(token),
        json={"notes": "Verified duplicate; removed stale upload."},
    )
    assert resp.status_code == 200
    resolved = resp.json()
    assert resolved["status"] == "resolved"
    assert resolved["resolution_notes"] == "Verified duplicate; removed stale upload."
    assert resolved["resolved_by"] == str(operator.id)

    # Resolving again is a conflict, not a silent no-op.
    resp = await client.post(
        f"/api/v1/escalations/{e1.id}/resolve",
        headers=_auth(token),
        json={"notes": "again"},
    )
    assert resp.status_code == 409

    # Both human actions must be recorded in the decision audit trail.
    resp = await client.get(
        "/api/v1/audit/decisions?action=escalation_resolved", headers=_auth(token)
    )
    assert resp.status_code == 200
    decisions = resp.json()["decisions"]
    assert len(decisions) == 1
    assert str(e1.id) in decisions[0]["reasoning"]
    assert decisions[0]["actor"] == f"human:{operator.id}"
    assert decisions[0]["record_hash"]

    resp = await client.get(
        "/api/v1/audit/decisions?action=escalation_acknowledged", headers=_auth(token)
    )
    assert resp.status_code == 200
    assert len(resp.json()["decisions"]) == 1

    # Stats reflect the worked item.
    resp = await client.get("/api/v1/escalations/stats", headers=_auth(token))
    assert resp.json()["by_status"]["resolved"] == 1
    assert resp.json()["by_status"]["open"] == 1

    # The Merkle chain over the day's decisions still verifies.
    resp = await client.post("/api/v1/audit/verify-chain", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


# ─── 2. Project onboarding over HTTP ─────────────────────────────────────────

_CSV_PAYLOAD = (
    "stove_id,household_id,usage_hours,fuel_consumed_kg,gps_latitude,gps_longitude,timestamp\n"
    "STV-001,HH-001,3.5,2.4,-1.2921,36.8219,2024-03-01T08:00:00\n"
    "STV-002,HH-002,4.0,2.8,-1.2905,36.8195,2024-03-01T08:15:00\n"
).encode()


class _FakeS3Client:
    """In-memory S3 double so the real upload/download code paths execute."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body, ContentType=None):  # noqa: N803
        self.objects[f"{Bucket}:{Key}"] = Body

    def get_object(self, Bucket, Key):  # noqa: N803
        from io import BytesIO

        return {"Body": BytesIO(self.objects[f"{Bucket}:{Key}"])}


class _CleanScanner:
    """ClamAV double reporting clean (no clamd in tests)."""

    async def scan_buffer(self, data: bytes):
        return clamav_module.ScanResult(status=clamav_module.ScanStatus.clean)


@pytest.mark.asyncio
async def test_project_onboarding_journey_over_http(
    client: AsyncClient,
    db_session: AsyncSession,
    engine,
    monkeypatch,
):
    """Developer is read-only for project creation (403); an operator drives
    create project → data source → CSV upload (real pipeline, inline via
    Celery eager) → calculation → retrieval → report list."""
    from app.config import get_settings
    from app.tasks import jobs as jobs_module
    from app.tasks.celery_app import celery_app

    developer = await _seed_user(db_session, UserRoleEnum.developer)
    developer_profile = await _seed_developer(db_session)

    # External-integration doubles: real code paths, no network.
    fake_s3 = _FakeS3Client()
    monkeypatch.setattr(boto3, "client", lambda *a, **k: fake_s3)
    monkeypatch.setattr(get_settings(), "S3_BUCKET_NAME", "e2e-test-bucket")
    monkeypatch.setattr(s3_module, "_s3_client", None)
    monkeypatch.setattr(clamav_module, "_scanner", _CleanScanner())
    # NOTE: conftest exports CELERY_TASK_ALWAYS_EAGER=True, but no app config
    # reads it — eager mode is OFF by default. Enable it here so
    # ``process_uploaded_file.delay()`` runs inline inside the request, which
    # is what conftest intended.
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    # The Celery task opens its own session via app.database.AsyncSessionLocal
    # (imported by name into app.tasks.jobs); point it at the test database so
    # inline processing mutates the same rows the API client sees.
    test_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(jobs_module, "AsyncSessionLocal", test_session)

    # ── Developer login works, but project creation is operator-gated. ──
    dev_token = await _login(client, developer.email)
    resp = await client.post(
        "/projects/",
        headers=_auth(dev_token),
        json={
            "name": "Developer Attempt",
            "methodology": "TPDDTEC_v4",
            "crediting_period_start": "2024-01-01",
            "crediting_period_end": "2030-12-31",
            "developer_id": str(developer_profile.id),
        },
    )
    assert resp.status_code == 403

    # ── Operator drives the onboarding journey. ──
    operator = await _seed_user(db_session, UserRoleEnum.operator)
    token = await _login(client, operator.email)

    resp = await client.post(
        "/projects/",
        headers=_auth(token),
        json={
            "name": "E2E Cookstove Project",
            "methodology": "TPDDTEC_v4",
            "crediting_period_start": "2024-01-01",
            "crediting_period_end": "2030-12-31",
            "developer_id": str(developer_profile.id),
        },
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # Add a validated data source carrying the parameters the calculation
    # engine needs (location, fuel, stove parameters).
    resp = await client.post(
        "/data-sources/",
        headers=_auth(token),
        json={
            "project_id": project_id,
            "source_type": "manual_entry",
            "schema_version": "manual_v1",
            "raw_data": {},
            "processed_data": {
                "project_location": [-1.2921, 36.8219],
                "fuel_type": "wood",
                "household_count": 500,
                "fuel_consumption_kg_per_day": 2.5,
                "thermal_efficiency": 0.30,
                "baseline_efficiency": 0.10,
            },
            "validation_status": "valid",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["validation_status"] == "valid"

    # Upload a small monitoring CSV via multipart. The processing task runs
    # inline (eager) and must complete end to end: S3 round-trip, virus scan,
    # pandas pipeline, validation, DataSource creation.
    resp = await client.post(
        f"/uploads/projects/{project_id}/upload",
        headers=_auth(token),
        files={"file": ("monitoring.csv", _CSV_PAYLOAD, "text/csv")},
        data={"source_type": "document"},
    )
    assert resp.status_code == 200
    upload_body = resp.json()
    assert upload_body["detected_type"] == "csv"
    file_id = upload_body["file_id"]

    # Downstream state after inline Celery processing.
    resp = await client.get(f"/uploads/{file_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    result = await db_session.execute(
        select(DataSource).where(DataSource.project_id == project_id)
    )
    data_sources = result.scalars().all()
    pipeline_sources = [
        ds for ds in data_sources if "upload_id" in (ds.raw_data or {})
    ]
    assert len(pipeline_sources) == 1, "upload pipeline must create a DataSource"
    assert pipeline_sources[0].processed_data, "pipeline must populate processed_data"

    # Trigger the calculation through the real route.
    resp = await client.post(
        f"/calculations/projects/{project_id}/calculate", headers=_auth(token)
    )
    assert resp.status_code == 200
    calc = resp.json()
    assert calc["status"] == "draft"
    assert 0 < calc["fnrb"]["fnrb_value"] <= 1.0
    assert calc["emissions"]["net_reductions"]["net_reduction_tco2e"] >= 0
    calculation_run_id = calc["calculation_run_id"]

    # Calculation result retrievable.
    resp = await client.get(f"/calculations/{calculation_run_id}", headers=_auth(token))
    assert resp.status_code == 200
    calc_run = resp.json()
    assert calc_run["status"] == "draft"
    assert calc_run["emissions_reduction_tCO2e"] is not None

    # Approve the calculation through the human approval gate.
    resp = await client.post(
        f"/calculations/{calculation_run_id}/approve", headers=_auth(token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Report list reflects the new report for this project.
    resp = await client.post(
        "/reports/",
        headers=_auth(token),
        json={
            "project_id": project_id,
            "calculation_run_id": calculation_run_id,
            "template_type": "GoldStandard_TPDDTEC",
        },
    )
    assert resp.status_code == 201
    resp = await client.get(
        f"/reports/?project_id={project_id}", headers=_auth(token)
    )
    assert resp.status_code == 200
    reports = resp.json()
    assert len(reports) == 1
    assert reports[0]["calculation_run_id"] == calculation_run_id


# ─── 3. VVB clarification loop ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vvb_clarification_loop(client: AsyncClient, db_session: AsyncSession):
    """Submitted project + outstanding VVB query → real vvb_liaison agent run
    over HTTP → drafted response recorded as an AgentDecision, auditable via
    /api/v1/audit/{decision_id} and the Merkle chain."""
    operator = await _seed_user(db_session, UserRoleEnum.operator)
    developer_profile = await _seed_developer(db_session)

    project = Project(
        id=uuid.uuid4(),
        name="VVB Loop Project",
        developer_id=developer_profile.id,
        methodology=MethodologyEnum.VM0050,
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2030, 12, 31),
        status=ProjectStatusEnum.submitted,
    )
    calc_run = CalculationRun(
        id=uuid.uuid4(),
        project_id=project.id,
        monitoring_period_start=date(2024, 1, 1),
        monitoring_period_end=date(2024, 12, 31),
        fNRB_value=0.42,
        emissions_reduction_tCO2e=1250.0,
        uncertainty_95CI=0.15,
        leakage_assessment={"total_leakage_tco2e": 12.5},
        methodology_compliance_score=0.9,
    )
    report = Report(
        id=uuid.uuid4(),
        project_id=project.id,
        calculation_run_id=calc_run.id,
        template_type=ReportTemplateTypeEnum.Verra_VM0050,
        draft_content={},
        status=ReportStatusEnum.submitted,
        vvb_feedback={"queries": ["What is the source of the fNRB value used?"]},
    )
    db_session.add_all([project, calc_run, report])
    await db_session.commit()

    token = await _login(client, operator.email)

    # Dispatch the REAL VVBLiaisonAgent (AGENT_REGISTRY) over HTTP. The agent
    # drafts a knowledge-base response to the outstanding VVB query and the
    # orchestrator records the routing decision in the audit chain.
    resp = await client.post(
        f"/orchestrator/projects/{project.id}/agents/vvb_liaison/run",
        headers=_auth(token),
        json={"report_id": str(report.id)},
    )
    assert resp.status_code == 200
    run = resp.json()
    assert run["status"] in ("completed", "queued_for_review")
    assert run["confidence_score"] is not None
    assert 0.0 <= run["confidence_score"] <= 1.0

    responses = run["output_data"]["responses"]
    assert responses, "agent must draft a response to the outstanding VVB query"
    drafted = responses[0]
    assert drafted["response_text"].strip()
    assert "fNRB" in drafted["response_text"]

    # The drafted response is auditable: an AgentDecision was recorded and is
    # retrievable by decision id with full context package.
    resp = await client.get(
        f"/api/v1/audit/decisions?project_id={project.id}&agent_type=vvb_liaison",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    decisions = resp.json()["decisions"]
    assert len(decisions) >= 1
    decision = decisions[0]
    assert decision["action"] in ("auto_advance", "queued_for_review", "escalated")
    assert decision["reasoning"]
    assert decision["confidence_score"] is not None

    resp = await client.get(
        f"/api/v1/audit/{decision['decision_id']}", headers=_auth(token)
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["agent_type"] == "vvb_liaison"
    assert detail["record_hash"]
    # The decision's context carries the agent's drafted responses.
    context = detail["context_package"] or {}
    output = context.get("output_data") or {}
    assert output.get("responses") or output.get("evidence", {}).get("answered_count", 0) >= 1

    # Legacy audit log also records the VVB handling surface.
    resp = await client.get("/audit/logs?limit=100", headers=_auth(token))
    assert resp.status_code == 200

    # Merkle chain integrity over everything recorded so far.
    resp = await client.post("/api/v1/audit/verify-chain", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


# ─── 4. Auth negatives ────────────────────────────────────────────────────────

NO_TOKEN_401_ENDPOINTS = [
    ("GET", "/api/v1/escalations/"),
    ("GET", "/api/v1/escalations/stats"),
    ("GET", "/api/v1/escalations/health/score"),
    ("GET", "/api/v1/audit/decisions"),
    ("GET", "/api/v1/remediation/rules"),
    ("GET", "/api/v1/remediation/attempts"),
    ("GET", "/api/v1/remediation/stats"),
    ("GET", "/api/v1/knowledge/documents"),
    ("POST", "/api/v1/knowledge/query"),
    ("GET", "/api/v1/knowledge/search?q=fnrb"),
    ("GET", "/api/v1/learning/calibration"),
    ("GET", "/api/v1/learning/report/weekly"),
    ("GET", "/api/v1/validation/health"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", NO_TOKEN_401_ENDPOINTS)
async def test_new_api_prefixes_require_token(client: AsyncClient, method, path):
    """Every new /api/v1 prefix rejects unauthenticated calls with 401."""
    resp = await client.request(method, path)
    assert resp.status_code == 401, f"{method} {path} must require auth"


@pytest.mark.asyncio
async def test_viewer_forbidden_on_operator_writes(
    client: AsyncClient, db_session: AsyncSession
):
    """Viewer role authenticates fine but cannot perform operator writes."""
    viewer = await _seed_user(db_session, UserRoleEnum.viewer)
    token = await _login(client, viewer.email)

    # Sanity: viewer CAN read viewer-gated surfaces.
    resp = await client.get("/api/v1/audit/decisions", headers=_auth(token))
    assert resp.status_code == 200
    resp = await client.get("/api/v1/validation/health", headers=_auth(token))
    assert resp.status_code == 200

    dummy = uuid.uuid4()
    forbidden = [
        ("POST", f"/api/v1/escalations/{dummy}/acknowledge", None),
        ("POST", f"/api/v1/escalations/{dummy}/resolve", {"notes": "x"}),
        ("POST", f"/api/v1/remediation/attempts/{dummy}/retry", None),
        (
            "POST",
            "/api/v1/knowledge/documents",
            {
                "registry": "gold_standard",
                "methodology_id": "M1",
                "title": "t",
                "content": "body",
                "version": "1.0",
            },
        ),
        ("POST", "/api/v1/learning/report/weekly/generate", None),
    ]
    for method, path, payload in forbidden:
        resp = await client.request(
            method, path, headers=_auth(token), json=payload
        )
        assert resp.status_code == 403, f"{method} {path} must reject viewers"


# ─── 5. Auth-gating tripwire ─────────────────────────────────────────────────

NEW_PREFIXES = (
    "/api/v1/audit",
    "/api/v1/escalations",
    "/api/v1/remediation",
    "/api/v1/knowledge",
    "/api/v1/learning",
    "/api/v1/validation/health",
)


def _iter_dependants(dependant):
    yield dependant
    for sub in dependant.dependencies:
        yield from _iter_dependants(sub)


def _route_has_auth(route) -> bool:
    for dep in _iter_dependants(route.dependant):
        call = dep.call
        if call is None:
            continue
        if isinstance(call, (RoleChecker, PermissionChecker)):
            return True
        module = getattr(call, "__module__", "") or ""
        if module.startswith("app.auth"):
            return True
    return False


def test_all_routes_under_new_prefixes_have_auth_dependency():
    """Regression tripwire: any route added under the new /api/v1 prefixes
    without an auth dependency fails here. If a route is intentionally
    public, add it to PUBLIC_ROUTES below with a comment."""
    public_routes: set[str] = set()  # none today — every route requires auth

    checked = 0
    uncovered: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not any(route.path.startswith(p) for p in NEW_PREFIXES):
            continue
        checked += 1
        if route.path in public_routes:
            continue
        if not _route_has_auth(route):
            methods = ",".join(sorted(route.methods or []))
            uncovered.append(f"{methods} {route.path}")

    assert checked >= 20, (
        f"tripwire found only {checked} routes under {NEW_PREFIXES} — "
        "app.routes reflection appears broken"
    )
    assert uncovered == [], (
        "routes under the new /api/v1 prefixes without an auth dependency:\n"
        + "\n".join(uncovered)
    )
