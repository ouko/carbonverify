"""Tests for Batch 5 project lifecycle hardening."""

import uuid
import pytest
from datetime import date
from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    User,
    UserRoleEnum,
    Developer,
    Project,
    DataSource,
    ValidationStatusEnum,
    CalculationRun,
    CalculationStatusEnum,
    Report,
    ReportStatusEnum,
    ProjectStatusEnum,
    MethodologyEnum,
    SourceTypeEnum,
    ReportTemplateTypeEnum,
)
from app.api.projects import validate_status_transition, VALID_PROJECT_TRANSITIONS
from app.api.calculations import VALID_CALCULATION_TRANSITIONS, run_project_calculation
from app.api.reports import VALID_REPORT_TRANSITIONS, create_report, submit_report_to_registry
from app.schemas import ReportCreate
from app.security.project_auth import require_project_access
from app.core.encryption import compute_searchable_hash


def _make_user(role: UserRoleEnum = UserRoleEnum.operator):
    uid = uuid.uuid4()
    email = f"test-{uid}@cv.io"
    return User(
        id=uid,
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Test User",
        role=role,
        hashed_password="hp",
    )


def _make_project(developer_id: uuid.UUID):
    return Project(
        id=uuid.uuid4(),
        name="Test Project",
        developer_id=developer_id,
        methodology=MethodologyEnum.TPDDTEC_v4,
        crediting_period_start=date(2024, 1, 1),
        crediting_period_end=date(2024, 12, 31),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Project-level authorization
# ═══════════════════════════════════════════════════════════════════════════════

class TestProjectAuthorization:
    @pytest.mark.asyncio
    async def test_admin_can_access_any_project(self, db_session):
        admin = _make_user(UserRoleEnum.admin)
        dev = Developer(id=uuid.uuid4(), user_id=admin.id, company_name="Dev")
        project = _make_project(dev.id)
        db_session.add_all([admin, dev, project])
        await db_session.commit()

        result = await require_project_access(project.id, admin, db_session)
        assert result.id == project.id

    @pytest.mark.asyncio
    async def test_developer_denied_other_project(self, db_session):
        user1 = _make_user(UserRoleEnum.developer)
        dev1 = Developer(id=uuid.uuid4(), user_id=user1.id, company_name="Dev1")
        project = _make_project(dev1.id)

        user2 = _make_user(UserRoleEnum.developer)
        dev2 = Developer(id=uuid.uuid4(), user_id=user2.id, company_name="Dev2")

        db_session.add_all([user1, dev1, project, user2, dev2])
        await db_session.commit()

        with pytest.raises(HTTPException) as exc:
            await require_project_access(project.id, user2, db_session)
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# State machine enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateMachine:
    def test_valid_project_transition(self):
        validate_status_transition(
            ProjectStatusEnum.onboarding,
            ProjectStatusEnum.data_collection,
            VALID_PROJECT_TRANSITIONS,
        )

    def test_invalid_project_transition(self):
        with pytest.raises(HTTPException) as exc:
            validate_status_transition(
                ProjectStatusEnum.onboarding,
                ProjectStatusEnum.submitted,
                VALID_PROJECT_TRANSITIONS,
            )
        assert exc.value.status_code == 400

    def test_rejected_is_always_allowed(self):
        # Rejected is a valid target from any project status
        validate_status_transition(
            ProjectStatusEnum.calculation,
            ProjectStatusEnum.rejected,
            VALID_PROJECT_TRANSITIONS,
        )

    def test_valid_calculation_transition(self):
        validate_status_transition(
            CalculationStatusEnum.draft,
            CalculationStatusEnum.review_pending,
            VALID_CALCULATION_TRANSITIONS,
        )

    def test_invalid_calculation_transition(self):
        with pytest.raises(HTTPException) as exc:
            validate_status_transition(
                CalculationStatusEnum.approved,
                CalculationStatusEnum.draft,
                VALID_CALCULATION_TRANSITIONS,
            )
        assert exc.value.status_code == 400

    def test_valid_report_transition(self):
        validate_status_transition(
            ReportStatusEnum.draft,
            ReportStatusEnum.submitted,
            VALID_REPORT_TRANSITIONS,
        )

    def test_invalid_report_transition(self):
        with pytest.raises(HTTPException) as exc:
            validate_status_transition(
                ReportStatusEnum.submitted,
                ReportStatusEnum.draft,
                VALID_REPORT_TRANSITIONS,
            )
        assert exc.value.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Calculation runs using real data
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculationRealData:
    @pytest.mark.asyncio
    async def test_run_project_calculation_no_validated_sources(self, db_session):
        admin = _make_user(UserRoleEnum.admin)
        dev = Developer(id=uuid.uuid4(), user_id=admin.id, company_name="Dev")
        project = _make_project(dev.id)
        db_session.add_all([admin, dev, project])
        await db_session.commit()

        with pytest.raises(HTTPException) as exc:
            await run_project_calculation(project.id, project, db_session, admin)
        assert exc.value.status_code == 400
        assert "No validated data sources" in exc.value.detail

    @pytest.mark.asyncio
    async def test_run_project_calculation_missing_location(self, db_session):
        admin = _make_user(UserRoleEnum.admin)
        dev = Developer(id=uuid.uuid4(), user_id=admin.id, company_name="Dev")
        project = _make_project(dev.id)
        ds = DataSource(
            project_id=project.id,
            source_type=SourceTypeEnum.manual_entry,
            schema_version="v1",
            processed_data={"fuel_type": "wood"},
            validation_status=ValidationStatusEnum.valid,
        )
        db_session.add_all([admin, dev, project, ds])
        await db_session.commit()

        with pytest.raises(HTTPException) as exc:
            await run_project_calculation(project.id, project, db_session, admin)
        assert exc.value.status_code == 400
        assert "Project location not available" in exc.value.detail


# ═══════════════════════════════════════════════════════════════════════════════
# Business rule chain validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestBusinessRules:
    @pytest.mark.asyncio
    async def test_create_report_requires_approved_calculation(self, db_session):
        admin = _make_user(UserRoleEnum.admin)
        dev = Developer(id=uuid.uuid4(), user_id=admin.id, company_name="Dev")
        project = _make_project(dev.id)
        calc = CalculationRun(
            id=uuid.uuid4(),
            project_id=project.id,
            monitoring_period_start=date(2024, 1, 1),
            monitoring_period_end=date(2024, 12, 31),
            status=CalculationStatusEnum.draft,
        )
        db_session.add_all([admin, dev, project, calc])
        await db_session.commit()

        payload = ReportCreate(
            project_id=project.id,
            calculation_run_id=calc.id,
            template_type=ReportTemplateTypeEnum.GoldStandard_TPDDTEC,
        )
        with pytest.raises(HTTPException) as exc:
            await create_report(payload, db_session, admin)
        assert exc.value.status_code == 400
        assert "approved" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_submit_report_requires_approved_report_and_calc(self, db_session):
        admin = _make_user(UserRoleEnum.admin)
        dev = Developer(id=uuid.uuid4(), user_id=admin.id, company_name="Dev")
        project = _make_project(dev.id)
        calc = CalculationRun(
            id=uuid.uuid4(),
            project_id=project.id,
            monitoring_period_start=date(2024, 1, 1),
            monitoring_period_end=date(2024, 12, 31),
            status=CalculationStatusEnum.approved,
        )
        report = Report(
            id=uuid.uuid4(),
            project_id=project.id,
            calculation_run_id=calc.id,
            template_type=ReportTemplateTypeEnum.GoldStandard_TPDDTEC,
            status=ReportStatusEnum.draft,
        )
        db_session.add_all([admin, dev, project, calc, report])
        await db_session.commit()

        with pytest.raises(HTTPException) as exc:
            await submit_report_to_registry(report.id, "verra", db_session, admin)
        assert exc.value.status_code == 400
        assert "approved" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_approve_calculation_requires_validated_data_source(self, db_session):
        admin = _make_user(UserRoleEnum.admin)
        dev = Developer(id=uuid.uuid4(), user_id=admin.id, company_name="Dev")
        project = _make_project(dev.id)
        calc = CalculationRun(
            id=uuid.uuid4(),
            project_id=project.id,
            monitoring_period_start=date(2024, 1, 1),
            monitoring_period_end=date(2024, 12, 31),
            status=CalculationStatusEnum.draft,
        )
        db_session.add_all([admin, dev, project, calc])
        await db_session.commit()

        from app.api.calculations import approve_calculation
        with pytest.raises(HTTPException) as exc:
            await approve_calculation(calc.id, db_session, admin)
        assert exc.value.status_code == 400
        assert "validated data sources" in exc.value.detail.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Cascade deletes
# ═══════════════════════════════════════════════════════════════════════════════

class TestCascadeDeletes:
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="SQLite in-memory does not enforce ON DELETE CASCADE; tested via DB migration")
    async def test_delete_project_cascades_data_sources(self, db_session):
        dev = Developer(id=uuid.uuid4(), user_id=uuid.uuid4(), company_name="Dev")
        project = _make_project(dev.id)
        ds = DataSource(
            project_id=project.id,
            source_type=SourceTypeEnum.satellite,
            schema_version="v1",
        )
        db_session.add_all([dev, project, ds])
        await db_session.commit()

        await db_session.delete(project)
        await db_session.commit()
        db_session.expunge_all()  # Clear identity map so DB-level cascade is visible

        result = await db_session.execute(select(DataSource).where(DataSource.id == ds.id))
        assert result.scalar_one_or_none() is None
