"""In-process service backing the synthetic journey ``service_call`` steps.

Registered on ``StepExecutorRegistry`` under the name ``validation_journeys``
so workflow graphs can invoke these methods without raw HTTP. Every method
opens its own session via ``app.database.get_db_context`` (imported at call
time) so tests can route sessions through the ``patch_db_context`` fixture.

The service deliberately creates small, marker-tagged in-DB fixtures so the
journeys are hermetic: no network, no external storage.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import compute_searchable_hash
from app.core.logging import get_logger
from app.validation_engine.executors import ServiceCallExecutor
from app.validation_engine.models import HumanEscalation

logger = get_logger(__name__)

SERVICE_NAME = "validation_journeys"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SyntheticJourneyService:
    """Named async service functions exercised by synthetic journey steps."""

    async def assert_true(self, value: Any, label: str = "assertion") -> dict[str, Any]:
        """Raise (failing the step and run) unless ``value`` is truthy.

        Chained after decision-gate steps: the gate evaluates the condition
        but never raises, so this step turns a false condition into a real
        workflow failure that tests and monitoring can see.
        """
        if value is True or value == "True" or value == "true":
            return {"assertion": label, "passed": True}
        raise RuntimeError(f"assertion_failed: {label}")

    # ─── developer journey ────────────────────────────────────────────────────

    async def register_developer(self, marker: str) -> dict[str, Any]:
        """Register a synthetic developer (User + Developer profile)."""
        from app.database import get_db_context
        from app.models import Developer, User, UserRoleEnum

        email = f"dev-{marker}@synth.carbonverify.test".lower()
        async with get_db_context() as db:
            user = User(
                email=email,
                email_hash=compute_searchable_hash(email),
                name=f"Synthetic Developer {marker}",
                role=UserRoleEnum.developer,
                mfa_enabled=False,
                hashed_password="synthetic-not-a-real-hash",
                is_active=True,
            )
            db.add(user)
            await db.flush()
            developer = Developer(
                user_id=user.id,
                company_name=f"Synthetic Ventures {marker}",
            )
            db.add(developer)
            await db.commit()
            await db.refresh(developer)
            return {
                "developer_id": str(developer.id),
                "user_id": str(user.id),
                "marker": marker,
            }

    async def create_project(self, developer_id: str, project_name: str) -> dict[str, Any]:
        """Create a project in onboarding state owned by the synthetic developer."""
        from app.database import get_db_context
        from app.models import MethodologyEnum, Project, ProjectStatusEnum

        async with get_db_context() as db:
            project = Project(
                developer_id=uuid.UUID(str(developer_id)),
                name=project_name,
                methodology=MethodologyEnum.VM0050,
                crediting_period_start=date(2024, 1, 1),
                crediting_period_end=date(2034, 1, 1),
                status=ProjectStatusEnum.onboarding,
            )
            db.add(project)
            await db.commit()
            await db.refresh(project)
            return {
                "project_id": str(project.id),
                "name": project.name,
                "status": project.status.value,
            }

    async def create_fixture_data(self, project_id: str, marker: str) -> dict[str, Any]:
        """Upload a small in-DB data fixture (one mobile-survey DataSource)."""
        from app.database import get_db_context
        from app.models import DataSource, SourceTypeEnum, ValidationStatusEnum

        async with get_db_context() as db:
            source = DataSource(
                project_id=uuid.UUID(str(project_id)),
                source_type=SourceTypeEnum.mobile_survey,
                schema_version="1.0",
                raw_data={
                    "fixture": True,
                    "actor_marker": marker,
                    "readings": [
                        {"household": f"HH-{i}", "fuel_baseline": "firewood", "stoves": 1}
                        for i in range(1, 6)
                    ],
                },
                processed_data={"stove_count": 5},
                validation_status=ValidationStatusEnum.valid,
                provenance={"source": "synthetic_journey", "actor_marker": marker},
                confidence_score=0.9,
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)
            return {
                "data_source_id": str(source.id),
                "fixture_rows": 5,
            }

    async def run_calculation(self, project_id: str) -> dict[str, Any]:
        """Run a synthetic calculation and walk the project to review state."""
        from app.database import get_db_context
        from app.models import (
            CalculationRun,
            CalculationStatusEnum,
            Project,
            ProjectStatusEnum,
        )

        transition_log = [ProjectStatusEnum.onboarding.value]
        async with get_db_context() as db:
            project = await db.get(Project, uuid.UUID(str(project_id)))
            if project is None:
                raise RuntimeError(f"Project {project_id} not found")

            for status in (
                ProjectStatusEnum.data_collection,
                ProjectStatusEnum.calculation,
                ProjectStatusEnum.review,
            ):
                project.status = status
                transition_log.append(status.value)
                await db.flush()

            calculation = CalculationRun(
                project_id=project.id,
                monitoring_period_start=date(2024, 1, 1),
                monitoring_period_end=date(2024, 12, 31),
                fNRB_value=0.85,
                emissions_reduction_tCO2e=120.5,
                uncertainty_95CI=4.2,
                leakage_assessment={"assessed": True, "leakage_tCO2e": 0.0},
                methodology_compliance_score=0.93,
                confidence_score=0.91,
                status=CalculationStatusEnum.review_pending,
            )
            db.add(calculation)
            await db.commit()
            await db.refresh(calculation)
            return {
                "calculation_id": str(calculation.id),
                "project_id": str(project.id),
                "project_status": project.status.value,
                "transition_log": transition_log,
            }

    async def generate_report_draft(
        self, project_id: str, calculation_id: str
    ) -> dict[str, Any]:
        """Generate a synthetic report draft for the calculation run."""
        from app.database import get_db_context
        from app.models import Report, ReportStatusEnum, ReportTemplateTypeEnum

        async with get_db_context() as db:
            report = Report(
                project_id=uuid.UUID(str(project_id)),
                calculation_run_id=uuid.UUID(str(calculation_id)),
                template_type=ReportTemplateTypeEnum.Verra_VM0050,
                draft_content={
                    "sections": ["baseline", "monitoring", "emissions_reduction"],
                    "generated_by": "synthetic_journey",
                },
                status=ReportStatusEnum.draft,
            )
            db.add(report)
            await db.commit()
            await db.refresh(report)
            return {
                "report_id": str(report.id),
                "status": report.status.value,
            }

    # ─── enumerator journey ───────────────────────────────────────────────────

    async def create_offline_batch(self, marker: str, project_name: str) -> dict[str, Any]:
        """Create an enumerator with an offline survey batch (6 rows, 1 duplicate)."""
        from app.database import get_db_context
        from app.models import (
            Enumerator,
            MethodologyEnum,
            Project,
            ProjectStatusEnum,
            SurveyResponse,
            User,
            UserRoleEnum,
            WhatsAppConversation,
        )

        async with get_db_context() as db:
            email = f"enum-{marker}@synth.carbonverify.test".lower()
            user = User(
                email=email,
                email_hash=compute_searchable_hash(email),
                name=f"Synthetic Field Manager {marker}",
                role=UserRoleEnum.operator,
                mfa_enabled=False,
                hashed_password="synthetic-not-a-real-hash",
                is_active=True,
            )
            db.add(user)
            await db.flush()

            project = Project(
                developer_id=(await self._ensure_developer(db, user.id)),
                name=project_name,
                methodology=MethodologyEnum.TPDDTEC_v4,
                crediting_period_start=date(2024, 1, 1),
                crediting_period_end=date(2030, 1, 1),
                status=ProjectStatusEnum.data_collection,
            )
            db.add(project)
            await db.flush()

            enumerator = Enumerator(
                project_id=project.id,
                name=f"Synthetic Enumerator {marker}",
                phone_number=f"+254700{uuid.uuid4().hex[:6]}",
                language_preference="sw",
                active=True,
            )
            db.add(enumerator)
            await db.flush()

            conversation = WhatsAppConversation(
                project_id=project.id,
                phone_number=enumerator.phone_number,
                language="sw",
                assigned_enumerator_id=enumerator.id,
            )
            db.add(conversation)
            await db.flush()

            # 5 unique households + 1 duplicate of HH-2 captured offline.
            households = ["HH-1", "HH-2", "HH-3", "HH-4", "HH-5", "HH-2"]
            now = _utcnow()
            for index, household in enumerate(households):
                response = SurveyResponse(
                    project_id=project.id,
                    conversation_id=conversation.id,
                    enumerator_id=enumerator.id,
                    household_id=household,
                    responses={"fuel_baseline": "firewood", "stove_in_use": "yes"},
                    gps_latitude=-1.2921 + index * 0.001,
                    gps_longitude=36.8219 + index * 0.001,
                    submitted_via="offline_survey",
                    created_at=now + timedelta(minutes=index),
                )
                db.add(response)

            enumerator.submissions_count = len(households)
            await db.commit()
            return {
                "project_id": str(project.id),
                "enumerator_id": str(enumerator.id),
                "offline_count": len(households),
            }

    async def _ensure_developer(self, db: AsyncSession, user_id: Any) -> Any:
        from app.models import Developer

        result = await db.execute(select(Developer).where(Developer.user_id == user_id))
        developer = result.scalar_one_or_none()
        if developer is None:
            developer = Developer(user_id=user_id, company_name="Synthetic Field Ops")
            db.add(developer)
            await db.flush()
        return developer.id

    async def sync_offline_batch(self, project_id: str, marker: str) -> dict[str, Any]:
        """Sync the offline batch: deduplicate households, stamp provenance.

        The newest row for a duplicated household wins; older duplicates are
        marked rejected with a provenance trail. No row is deleted.
        """
        from app.database import get_db_context
        from app.models import SurveyResponse, ValidationStatusEnum

        async with get_db_context() as db:
            result = await db.execute(
                select(SurveyResponse)
                .where(
                    SurveyResponse.project_id == uuid.UUID(str(project_id)),
                    SurveyResponse.submitted_via == "offline_survey",
                )
                .order_by(SurveyResponse.created_at.asc())
            )
            rows: list[SurveyResponse] = list(result.scalars().all())
            if not rows:
                raise RuntimeError(f"No offline survey rows found for project {project_id}")

            seen: dict[str, SurveyResponse] = {}
            conflicts_resolved = 0
            synced = 0
            for row in rows:
                household = row.household_id or str(row.id)
                if household in seen:
                    # Conflict: keep the newest, reject the older duplicate.
                    older = seen[household]
                    older.validation_status = ValidationStatusEnum.rejected
                    older.validation_errors = ["duplicate_superseded_by_sync"]
                    older.responses = {
                        **(older.responses or {}),
                        "sync_provenance": {
                            "method": "conflict_resolution",
                            "superseded_by": str(row.id),
                            "synced_by": marker,
                            "synced_at": _utcnow().isoformat(),
                        },
                    }
                    conflicts_resolved += 1
                else:
                    seen[household] = row

                row.submitted_via = "whatsapp"
                row.responses = {
                    **(row.responses or {}),
                    "sync_provenance": {
                        "method": "offline_to_sync",
                        "synced_by": marker,
                        "synced_at": _utcnow().isoformat(),
                    },
                }
                synced += 1

            await db.commit()
            return {
                "offline_found": len(rows),
                "synced": synced,
                "conflicts_resolved": conflicts_resolved,
                "total_preserved": len(rows),
                "data_loss": False,
                "provenance_recorded": True,
            }

    # ─── calculation anomaly recovery journey ─────────────────────────────────

    async def inject_and_remediate_anomaly(
        self, marker: str, target_name: str
    ) -> dict[str, Any]:
        """Inject a calculation anomaly and prove the auto-remediation path.

        A shared-engine remediation round is run with an injected attempt
        function whose first attempt fails and second succeeds. Records the
        before/after state hashes from the engine outcome.
        """
        from app.database import get_db_context
        from app.remediation.engine import RemediationEngine
        from app.remediation.rules import seed_default_rules

        target_id = f"calc-anomaly-{marker}-{target_name}"
        failing_state = {
            "service": "calculation_engine",
            "error": "synthetic_injected_anomaly",
            "value": 99999.0,
            "marker": marker,
        }

        async with get_db_context() as db:
            await seed_default_rules(db)

            attempts = {"count": 0}

            async def attempt_fn(ctx: Any) -> bool:
                # Deterministic failure injection: first attempt fails,
                # second succeeds — proving the retry/remediation path.
                attempts["count"] += 1
                return attempts["count"] >= 2

            engine = RemediationEngine(db, attempt_fn=attempt_fn)
            outcome = await engine.remediate(
                "api_timeout_rate_limit",
                "calculation",
                target_id,
                failing_state,
            )
            return {
                "target_id": target_id,
                "status": outcome.status,
                "rule_key": outcome.rule_key,
                "attempts_used": outcome.attempts_used,
                "before_state_hash": outcome.before_hash,
                "after_state_hash": outcome.after_hash,
            }

    async def count_escalations_for_target(self, target_id: str) -> dict[str, Any]:
        """Count human escalations tied to a remediation target (must be 0)."""
        from app.database import get_db_context
        from app.escalations.models import EscalationEvent, EscalationStatus
        from app.models import HumanReviewQueue

        async with get_db_context() as db:
            human_escalations = (
                await db.execute(
                    select(func.count(HumanEscalation.id)).where(
                        HumanEscalation.escalation_reason.contains(target_id)
                    )
                )
            ).scalar() or 0
            events = (
                await db.execute(
                    select(func.count(EscalationEvent.id)).where(
                        EscalationEvent.detail.contains(target_id),
                        EscalationEvent.status != EscalationStatus.resolved,
                    )
                )
            ).scalar() or 0
            review_items = (
                await db.execute(
                    select(func.count(HumanReviewQueue.id)).where(
                        HumanReviewQueue.reason.contains(target_id)
                    )
                )
            ).scalar() or 0
            return {
                "target_id": target_id,
                "escalations": int(human_escalations) + int(events) + int(review_items),
            }


# Module-level singleton registered on the executor registry. The runner
# module imports this module at worker start, so registration happens there;
# tests import it explicitly.
journey_service = SyntheticJourneyService()


def ensure_journey_service_registered() -> None:
    ServiceCallExecutor.register_service(SERVICE_NAME, journey_service)
