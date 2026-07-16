"""Seed script for CarbonVerify demo data.

Usage:
    cd backend && source .venv/bin/activate
    python -m scripts.seed_demo_data

Creates a rich demo environment with users, projects, data sources,
calculations, reports, review queue items, brokerage listings,
tokenization records, compliance data, leads, and more.

All users have password: "DemoPass123!"
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

# Ensure the backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ENVIRONMENT", "development")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, engine
from app.models import (
    AgentRun,
    AgentStatusEnum,
    AgentTypeEnum,
    AuditActionEnum,
    AuditLog,
    BreachNotification,
    BreachStatusEnum,
    BrokerageListing,
    BrokerageTransaction,
    BuyerProfile,
    BuyerTypeEnum,
    CalculationRun,
    CalculationStatusEnum,
    CarbonCreditToken,
    Commission,
    ConflictOfInterest,
    ConsentRecord,
    ConsentTypeEnum,
    ConversationFlowEnum,
    ConversationStateEnum,
    CorporatePortfolio,
    DataSource,
    DataSubjectRequest,
    Developer,
    DetectedFileTypeEnum,
    DSRStatusEnum,
    DSRTypeEnum,
    Enumerator,
    Escrow,
    FileUpload,
    FileUploadStatusEnum,
    HumanReviewQueue,
    Lead,
    LeadPriorityEnum,
    LeadProjectStatusEnum,
    LeadRegistrySourceEnum,
    LeadWorkflowStatusEnum,
    ListingStatusEnum,
    MethodologyEnum,
    MethodologyTemplate,
    MethodologyVersion,
    OrchestratorEvent,
    OrchestratorEventTypeEnum,
    PortfolioHolding,
    Project,
    ProjectStatusEnum,
    QueueItemTypeEnum,
    QueueStatusEnum,
    Report,
    ReportStatusEnum,
    ReportTemplateTypeEnum,
    SourceTypeEnum,
    SupportTicket,
    SurveyResponse,
    TokenListing,
    TokenRetirement,
    TokenStatusEnum,
    TradeMatch,
    TradeTypeEnum,
    TransactionStatusEnum,
    User,
    UserRoleEnum,
    ValidationStatusEnum,
    WhatsAppConversation,
)
from app.auth.security import get_password_hash
from app.core.encryption import compute_searchable_hash

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

DEMO_PASSWORD = "DemoPass123!"
DEMO_PASSWORD_HASH = get_password_hash(DEMO_PASSWORD)

KENYA_COUNTIES = [
    "Nairobi", "Mombasa", "Kisumu", "Nakuru", "Kiambu", "Kajiado",
    "Machakos", "Kakamega", "Bungoma", "Meru", "Nyeri", "Murang'a",
]

VILLAGES = [
    "Kibera", "Mathare", "Kawangware", "Dagoretti", "Embakasi",
    "Ruiru", "Thika", "Karatina", "Othaya", "Mweiga", "Nanyuki",
    "Isiolo", "Marsabit", "Moyale", "Mandera", "Wajir", "Garissa",
]

STOVE_TYPES = ["Envirofit CK-2020", "BURN Jikokoa", "EcoZoom Dura", "SupaSigdi", "Champion Cool"]

FUEL_TYPES = ["wood", "charcoal", "kerosene", "lpg", "crop_residue"]

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def now() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return now() - timedelta(days=n)


def rand_date(start: date, end: date) -> date:
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


def rand_float(min_val: float, max_val: float, decimals: int = 2) -> float:
    return round(random.uniform(min_val, max_val), decimals)


# ──────────────────────────────────────────────────────────────────────────────
# Seeding functions
# ──────────────────────────────────────────────────────────────────────────────


async def seed_users(db: AsyncSession) -> list[User]:
    """Create demo users across all roles (idempotent)."""
    users_data = [
        ("admin@carbonverify.demo", "Admin User", UserRoleEnum.admin),
        ("operator@carbonverify.demo", "Sarah Operator", UserRoleEnum.operator),
        ("developer@carbonverify.demo", "John Developer", UserRoleEnum.developer),
        ("viewer@carbonverify.demo", "Alice Viewer", UserRoleEnum.viewer),
        ("buyer@carbonverify.demo", "GreenCorp Buyer", UserRoleEnum.viewer),
        ("seller@carbonverify.demo", "EcoStove Seller", UserRoleEnum.developer),
        ("compliance@carbonverify.demo", "Mary Compliance", UserRoleEnum.operator),
        ("field@carbonverify.demo", "James Field Ops", UserRoleEnum.operator),
    ]

    existing_result = await db.execute(select(User))
    existing = {u.email: u for u in existing_result.scalars().all()}

    users: list[User] = []
    for email, name, role in users_data:
        if email in existing:
            users.append(existing[email])
            continue
        user = User(
            email=email,
            email_hash=compute_searchable_hash(email),
            name=name,
            role=role,
            hashed_password=DEMO_PASSWORD_HASH,
            mfa_enabled=False,
            failed_login_count=0,
            last_login_at=days_ago(random.randint(0, 7)),
            settings={
                "theme": "light",
                "email_notifications": True,
                "notifyHumanReview": True,
                "notifyVVB": True,
                "notifyAnomaly": True,
                "channelEmail": True,
                "channelInApp": True,
            },
        )
        db.add(user)
        users.append(user)

    await db.flush()
    print(f"✅ Ensured {len(users)} demo users")
    return users


async def seed_developers(db: AsyncSession, users: list[User]) -> list[Developer]:
    """Create developer profiles for developer-role users."""
    dev_users = [u for u in users if u.role == UserRoleEnum.developer]
    companies = ["EcoStove Kenya Ltd", "CarbonClear Africa", "GreenFire Projects"]

    developers: list[Developer] = []
    for i, user in enumerate(dev_users):
        dev = Developer(
            user_id=user.id,
            company_name=companies[i % len(companies)],
            contact_phone=None,  # EncryptedString(50) too small for Fernet ciphertext
            location=random.choice(KENYA_COUNTIES),
        )
        db.add(dev)
        developers.append(dev)

    await db.flush()
    print(f"✅ Created {len(developers)} developer profiles")
    return developers


async def seed_projects(db: AsyncSession, developers: list[Developer]) -> list[Project]:
    """Create carbon credit projects with various methodologies and statuses."""
    project_data = [
        {
            "name": "Kisumu Improved Cookstoves VCS-PDD",
            "methodology": MethodologyEnum.TPDDTEC_v4,
            "status": ProjectStatusEnum.verified,
            "brokerage_enabled": True,
            "tokenization_enabled": True,
        },
        {
            "name": "Nakuru Household Energy Efficiency",
            "methodology": MethodologyEnum.VM0050,
            "status": ProjectStatusEnum.monitoring,
            "brokerage_enabled": True,
            "tokenization_enabled": True,
        },
        {
            "name": "Kakamega Community Stove Programme",
            "methodology": MethodologyEnum.AMS_II_G,
            "status": ProjectStatusEnum.review,
            "brokerage_enabled": False,
            "tokenization_enabled": False,
        },
        {
            "name": "Kiambu Clean Cooking Initiative",
            "methodology": MethodologyEnum.TPDDTEC_v4,
            "status": ProjectStatusEnum.calculation,
            "brokerage_enabled": False,
            "tokenization_enabled": False,
        },
        {
            "name": "Mombasa Urban Stove Replacement",
            "methodology": MethodologyEnum.VMR0006,
            "status": ProjectStatusEnum.data_collection,
            "brokerage_enabled": False,
            "tokenization_enabled": False,
        },
        {
            "name": "Nairobi Slum Energy Upgrade",
            "methodology": MethodologyEnum.AMS_II_G,
            "status": ProjectStatusEnum.onboarding,
            "brokerage_enabled": False,
            "tokenization_enabled": False,
        },
    ]

    projects: list[Project] = []
    for pdata in project_data:
        dev = random.choice(developers)
        start = rand_date(date(2020, 1, 1), date(2023, 1, 1))
        end = start + timedelta(days=random.randint(365 * 5, 365 * 10))

        project = Project(
            developer_id=dev.id,
            name=pdata["name"],
            methodology=pdata["methodology"],
            status=pdata["status"],
            crediting_period_start=start,
            crediting_period_end=end,
            complexity_score=rand_float(0.3, 0.95),
            confidence_threshold=0.85,
            brokerage_enabled=pdata["brokerage_enabled"],
            tokenization_enabled=pdata["tokenization_enabled"],
            created_at=days_ago(random.randint(30, 500)),
        )
        db.add(project)
        projects.append(project)

    await db.flush()
    print(f"✅ Created {len(projects)} projects")
    return projects


async def seed_data_sources(db: AsyncSession, projects: list[Project]) -> list[DataSource]:
    """Create data sources for each project."""
    sources: list[DataSource] = []

    for project in projects:
        n_sources = random.randint(2, 6)
        for _ in range(n_sources):
            source_type = random.choice(list(SourceTypeEnum))
            raw = _generate_raw_data(source_type)
            processed = _generate_processed_data(source_type, raw)

            ds = DataSource(
                project_id=project.id,
                source_type=source_type,
                schema_version="1.2.0",
                raw_data=raw,
                processed_data=processed,
                validation_status=random.choice(list(ValidationStatusEnum)),
                validation_errors=None if random.random() > 0.3 else ["GPS coordinates slightly off", "Photo quality low"],
                provenance={
                    "collected_by": random.choice(["enumerator_001", "satellite_api", "iot_device"]),
                    "collection_date": days_ago(random.randint(1, 60)).isoformat(),
                    "verified_by": "auto",
                },
                confidence_score=rand_float(0.6, 0.99),
                created_at=days_ago(random.randint(1, 90)),
            )
            db.add(ds)
            sources.append(ds)

    await db.flush()
    print(f"✅ Created {len(sources)} data sources")
    return sources


def _generate_raw_data(source_type: SourceTypeEnum) -> dict:
    if source_type == SourceTypeEnum.satellite:
        return {
            "satellite_id": f"S2_{random.randint(100000, 999999)}",
            "capture_date": days_ago(random.randint(1, 30)).isoformat(),
            "resolution_m": 10,
            "bands": ["NDVI", "NIR", "RED"],
            "cloud_cover_pct": rand_float(0, 15),
            "aoi_km2": rand_float(10, 500),
        }
    elif source_type == SourceTypeEnum.iot:
        return {
            "device_id": f"IOT-{random.randint(1000, 9999)}",
            "sensor_type": random.choice(["temperature", "usage_hours", "fuel_level"]),
            "readings": [
                {"timestamp": days_ago(i).isoformat(), "value": rand_float(20, 100)}
                for i in range(random.randint(5, 20))
            ],
            "battery_pct": rand_float(30, 100),
        }
    elif source_type == SourceTypeEnum.mobile_survey:
        return {
            "enumerator_id": f"ENUM-{random.randint(10, 99)}",
            "household_id": f"HH-{random.randint(1000, 9999)}",
            "village": random.choice(VILLAGES),
            "county": random.choice(KENYA_COUNTIES),
            "stove_type": random.choice(STOVE_TYPES),
            "fuel_type_before": random.choice(FUEL_TYPES),
            "fuel_type_after": random.choice(FUEL_TYPES),
            "family_size": random.randint(2, 8),
            "cooking_frequency": random.choice(["3x_daily", "2x_daily", "daily"]),
        }
    elif source_type == SourceTypeEnum.document:
        return {
            "document_type": random.choice(["monitoring_report", "kpt_results", "sales_receipt"]),
            "filename": f"doc_{random.randint(1000, 9999)}.pdf",
            "pages": random.randint(5, 50),
            "extracted_text_length": random.randint(500, 5000),
        }
    else:  # manual_entry
        return {
            "entered_by": random.choice(["admin", "operator", "field_team"]),
            "data_category": random.choice(["baseline", "monitoring", "verification"]),
            "values": {
                "stoves_distributed": random.randint(100, 5000),
                "households_reached": random.randint(100, 5000),
                "tCO2e_estimated": rand_float(100, 10000),
            },
        }


def _generate_processed_data(source_type: SourceTypeEnum, raw: dict) -> dict:
    return {
        "processed_at": now().isoformat(),
        "pipeline_version": "2.1.0",
        "quality_score": rand_float(0.7, 0.99),
        "anomalies_detected": random.randint(0, 3),
        "summary": {
            "source_type": source_type.value,
            "record_count": random.randint(50, 5000),
            "field_coverage_pct": rand_float(85, 100),
        },
    }


async def seed_calculations(db: AsyncSession, projects: list[Project], users: list[User]) -> list[CalculationRun]:
    """Create calculation runs for projects."""
    calcs: list[CalculationRun] = []
    operators = [u for u in users if u.role in (UserRoleEnum.admin, UserRoleEnum.operator)]

    for project in projects:
        if project.status in (ProjectStatusEnum.onboarding, ProjectStatusEnum.data_collection):
            continue

        n_calcs = random.randint(1, 3)
        for i in range(n_calcs):
            start = rand_date(date(2023, 1, 1), date(2024, 6, 1))
            end = start + timedelta(days=random.randint(90, 365))

            fnrb = rand_float(0.6, 0.95)
            emissions = rand_float(500, 15000)

            calc = CalculationRun(
                project_id=project.id,
                monitoring_period_start=start,
                monitoring_period_end=end,
                fNRB_value=fnrb,
                emissions_reduction_tCO2e=emissions,
                uncertainty_95CI=rand_float(0.05, 0.25),
                leakage_assessment={
                    "leakage_pct": rand_float(2, 8),
                    "leakage_tCO2e": round(emissions * random.uniform(0.02, 0.08), 2),
                    "mitigation_measures": ["community_training", "fuel_monitoring"],
                },
                methodology_compliance_score=rand_float(0.75, 0.98),
                confidence_score=rand_float(0.7, 0.95),
                status=random.choice(list(CalculationStatusEnum)),
                approved_by=random.choice(operators).id if random.random() > 0.5 else None,
                created_at=days_ago(random.randint(1, 120)),
            )
            db.add(calc)
            calcs.append(calc)

    await db.flush()
    print(f"✅ Created {len(calcs)} calculation runs")
    return calcs


async def seed_reports(db: AsyncSession, projects: list[Project], calcs: list[CalculationRun]) -> list[Report]:
    """Create reports linked to calculation runs."""
    reports: list[Report] = []

    for calc in calcs:
        if calc.status != CalculationStatusEnum.approved:
            continue

        n_reports = random.randint(1, 2)
        for _ in range(n_reports):
            report = Report(
                project_id=calc.project_id,
                calculation_run_id=calc.id,
                template_type=random.choice(list(ReportTemplateTypeEnum)),
                draft_content={
                    "executive_summary": "This report summarizes the emissions reductions achieved...",
                    "methodology_applied": calc.project.methodology.value if calc.project else "TPDDTEC_v4",
                    "monitoring_period": f"{calc.monitoring_period_start} to {calc.monitoring_period_end}",
                    "total_reduction_tCO2e": calc.emissions_reduction_tCO2e,
                    "uncertainty_analysis": f"95% CI: ±{calc.uncertainty_95CI}%",
                    "sections": ["introduction", "baseline", "monitoring", "calculations", "uncertainty", "conclusion"],
                },
                final_pdf=None,
                status=random.choice(list(ReportStatusEnum)),
                vvb_feedback=None if random.random() > 0.3 else {
                    "vvb_name": random.choice(["TÜV SÜD", "SGS", "Bureau Veritas"]),
                    "requested_clarifications": ["Provide additional fuel consumption data", "Clarify leakage boundary"],
                    "response_deadline": (now() + timedelta(days=14)).isoformat(),
                },
                created_at=days_ago(random.randint(1, 60)),
            )
            db.add(report)
            reports.append(report)

    await db.flush()
    print(f"✅ Created {len(reports)} reports")
    return reports


async def seed_review_queue(
    db: AsyncSession, projects: list[Project], calcs: list[CalculationRun], reports: list[Report], users: list[User]
) -> list[HumanReviewQueue]:
    """Create human review queue items."""
    items: list[HumanReviewQueue] = []
    operators = [u for u in users if u.role in (UserRoleEnum.admin, UserRoleEnum.operator)]

    queue_reasons = [
        (QueueItemTypeEnum.calculation, "Confidence score below threshold — manual review required"),
        (QueueItemTypeEnum.report, "VVB requested clarification on methodology compliance"),
        (QueueItemTypeEnum.data_anomaly, "Outlier detected in fuel consumption data"),
        (QueueItemTypeEnum.agent_review, "Agent flagged potential double-counting risk"),
        (QueueItemTypeEnum.vvb_response, "New VVB feedback received — needs operator response"),
    ]

    for _ in range(random.randint(8, 15)):
        item_type, reason = random.choice(queue_reasons)
        if item_type == QueueItemTypeEnum.calculation and calcs:
            item_id = random.choice(calcs).id
        elif item_type == QueueItemTypeEnum.report and reports:
            item_id = random.choice(reports).id
        else:
            item_id = random.choice(projects).id

        status = random.choice(list(QueueStatusEnum))
        resolved_at = now() if status == QueueStatusEnum.resolved else None
        response_time = random.randint(300, 86400) if status == QueueStatusEnum.resolved else None

        qitem = HumanReviewQueue(
            item_type=item_type,
            item_id=item_id,
            reason=reason,
            priority=random.randint(1, 5),
            priority_score=rand_float(0.1, 0.99),
            sla_deadline=now() + timedelta(days=random.randint(1, 14)),
            assigned_to=random.choice(operators).id if operators else None,
            status=status,
            resolution_notes="Reviewed and approved after verification" if status == QueueStatusEnum.resolved else None,
            context_json={"project_name": random.choice(projects).name, "reviewer_notes": "Check fuel baseline"},
            suggested_action=random.choice(["approve", "reject", "request_more_data", "escalate"]),
            confidence_gap=rand_float(0.05, 0.3),
            human_decision="approved" if status == QueueStatusEnum.resolved else None,
            learning_feedback={"model_version": "v2.1", "correction_type": "false_positive"} if status == QueueStatusEnum.resolved else None,
            time_in_queue_seconds=random.randint(60, 3600 * 48),
            response_time_seconds=response_time,
            created_at=days_ago(random.randint(1, 30)),
            resolved_at=resolved_at,
        )
        db.add(qitem)
        items.append(qitem)

    await db.flush()
    print(f"✅ Created {len(items)} review queue items")
    return items


async def seed_agent_runs(db: AsyncSession, projects: list[Project]) -> list[AgentRun]:
    """Create orchestrator agent runs."""
    agents: list[AgentRun] = []
    agent_types = list(AgentTypeEnum)

    for project in projects:
        n_runs = random.randint(2, 8)
        for _ in range(n_runs):
            agent_type = random.choice(agent_types)
            status = random.choice(list(AgentStatusEnum))

            run = AgentRun(
                project_id=project.id,
                agent_type=agent_type,
                status=status,
                trigger_event=random.choice(["data_uploaded", "calculation_requested", "report_due", "vvb_feedback"]),
                input_data={"project_id": str(project.id), "methodology": project.methodology.value},
                output_data={"result": "success", "records_processed": random.randint(10, 500)} if status == AgentStatusEnum.completed else {},
                confidence_score=rand_float(0.6, 0.99) if status == AgentStatusEnum.completed else None,
                execution_time_ms=random.randint(500, 30000),
                error_message=None if status != AgentStatusEnum.failed else "Timeout during external API call",
                created_at=days_ago(random.randint(1, 60)),
                completed_at=now() if status in (AgentStatusEnum.completed, AgentStatusEnum.failed) else None,
            )
            db.add(run)
            agents.append(run)

    await db.flush()
    print(f"✅ Created {len(agents)} agent runs")
    return agents


async def seed_orchestrator_events(db: AsyncSession, projects: list[Project], agents: list[AgentRun]) -> None:
    """Create orchestrator events."""
    event_types = list(OrchestratorEventTypeEnum)
    events: list[OrchestratorEvent] = []

    for project in projects:
        n_events = random.randint(3, 10)
        for _ in range(n_events):
            event_type = random.choice(event_types)
            agent = random.choice(agents) if agents else None

            event = OrchestratorEvent(
                project_id=project.id,
                event_type=event_type,
                from_state=random.choice(["onboarding", "data_collection", "calculation", "review"]),
                to_state=random.choice(["data_collection", "calculation", "review", "submitted", "verified"]),
                agent_run_id=agent.id if agent and random.random() > 0.5 else None,
                confidence_score=rand_float(0.7, 0.98),
                details={"auto_advance": random.choice([True, False]), "reason": "Confidence threshold met"},
                created_at=days_ago(random.randint(1, 90)),
            )
            db.add(event)
            events.append(event)

    await db.flush()
    print(f"✅ Created {len(events)} orchestrator events")


async def seed_audit_logs(db: AsyncSession, users: list[User], projects: list[Project]) -> None:
    """Create audit log entries."""
    actions = list(AuditActionEnum)
    logs: list[AuditLog] = []

    for i in range(random.randint(30, 50)):
        actor = random.choice(users)
        target = random.choice(projects)
        # Anchor ~30% of logs to Radix so Verify buttons appear
        should_anchor = random.random() < 0.3

        log = AuditLog(
            action_type=random.choice(actions),
            actor_id=actor.id,
            actor_type="user",
            target_type=random.choice(["project", "calculation", "report", "user"]),
            target_id=target.id,
            timestamp=days_ago(random.randint(1, 90)),
            input_hash=f"sha256:{uuid.uuid4().hex}" if should_anchor else None,
            output_hash=f"sha256:{uuid.uuid4().hex}" if should_anchor else None,
            radix_tx_ref=f"tx_{uuid.uuid4().hex[:16]}" if should_anchor else None,
            reasoning="Automated action via demo seed script",
            metadata_json={"seed": True, "demo": True, "anchored": should_anchor},
            ip_address=f"192.168.1.{random.randint(10, 200)}",
            user_agent="Mozilla/5.0 (DemoSeed/1.0)",
        )
        db.add(log)
        logs.append(log)

    await db.flush()
    print(f"✅ Created {len(logs)} audit log entries ({sum(1 for l in logs if l.radix_tx_ref)} anchored)")


async def seed_compliance(db: AsyncSession, projects: list[Project], users: list[User]) -> None:
    """Create compliance data: consent records, DSRs, breaches, conflicts."""
    # Consent records
    consent_types = list(ConsentTypeEnum)
    for _ in range(random.randint(10, 20)):
        consent = ConsentRecord(
            subject_id=f"HH-{random.randint(1000, 9999)}",
            subject_type=random.choice(["enumerator", "household", "developer"]),
            consent_type=random.choice(consent_types),
            granted=random.choice([True, True, True, False]),  # 75% granted
            granted_at=days_ago(random.randint(1, 200)),
            revoked_at=days_ago(random.randint(1, 30)) if random.random() < 0.1 else None,
            project_id=random.choice(projects).id if random.random() > 0.3 else None,
            method=random.choice(["explicit", "implied", "verbal"]),
            metadata_json={"language": "sw", "witness_present": random.choice([True, False])},
        )
        db.add(consent)

    # Data Subject Requests
    dsr_types = list(DSRTypeEnum)
    dsr_statuses = list(DSRStatusEnum)
    for _ in range(random.randint(5, 10)):
        dsr = DataSubjectRequest(
            request_type=random.choice(dsr_types),
            status=random.choice(dsr_statuses),
            subject_id=f"SUB-{random.randint(1000, 9999)}",
            subject_type=random.choice(["household", "enumerator", "developer"]),
            description="Request submitted via WhatsApp bot",
            assigned_to=random.choice(users).id if random.random() > 0.5 else None,
            sla_deadline=now() + timedelta(days=30),
            fulfilled_at=days_ago(random.randint(1, 10)) if random.random() < 0.3 else None,
            fulfillment_notes="Data exported and sent via secure link" if random.random() < 0.3 else None,
            rejection_reason=None if random.random() > 0.2 else "Identity verification failed",
            created_at=days_ago(random.randint(1, 60)),
        )
        db.add(dsr)

    # Breach notifications
    breach_statuses = list(BreachStatusEnum)
    for _ in range(random.randint(2, 5)):
        breach = BreachNotification(
            title=random.choice([
                "Unauthorized access to enumerator database",
                "Email disclosure in batch export",
                "Temporary S3 bucket misconfiguration",
            ]),
            description="Incident detected during routine security audit. Immediate containment applied.",
            severity=random.choice(["low", "medium", "high", "critical"]),
            status=random.choice(breach_statuses),
            detected_at=days_ago(random.randint(1, 90)),
            detected_by=random.choice(users).id,
            affected_subjects_count=random.randint(0, 500),
            affected_data_types=["phone_numbers", "photos"],
            containment_measures="Access revoked, credentials rotated, audit initiated.",
            regulator_notified_at=days_ago(random.randint(1, 10)) if random.random() > 0.5 else None,
            subjects_notified_at=days_ago(random.randint(1, 10)) if random.random() > 0.5 else None,
            resolved_at=days_ago(random.randint(1, 5)) if random.random() > 0.7 else None,
            created_at=days_ago(random.randint(1, 90)),
        )
        db.add(breach)

    # Conflicts of interest
    for _ in range(random.randint(2, 4)):
        coi = ConflictOfInterest(
            user_id=random.choice(users).id,
            project_id=random.choice(projects).id,
            relationship_type=random.choice(["financial", "familial", "employment", "other"]),
            description="Disclosed potential conflict during project onboarding",
            disclosed_at=days_ago(random.randint(1, 180)),
            reviewed_by=random.choice(users).id if random.random() > 0.3 else None,
            approved=random.choice([True, False, None]),
            review_notes="No material conflict identified" if random.random() > 0.5 else "Under review",
        )
        db.add(coi)

    await db.flush()
    print("✅ Created compliance data (consent, DSRs, breaches, COI)")


async def seed_brokerage(
    db: AsyncSession, projects: list[Project], users: list[User], calcs: list[CalculationRun]
) -> None:
    """Create brokerage listings, buyer profiles, transactions, matches."""
    # Listings
    listings: list[BrokerageListing] = []
    verified_projects = [p for p in projects if p.status == ProjectStatusEnum.verified and p.brokerage_enabled]
    sellers = [u for u in users if u.role == UserRoleEnum.developer]

    for project in verified_projects:
        if not sellers:
            break
        seller = random.choice(sellers)
        for _ in range(random.randint(1, 3)):
            listing = BrokerageListing(
                project_id=project.id,
                seller_id=seller.id,
                available_credits=rand_float(1000, 50000),
                price_per_credit_usd=rand_float(5, 25),
                vintage_year=random.randint(2020, 2024),
                methodology=project.methodology.value,
                co_benefits=random.sample(["health", "gender_equality", "biodiversity", "education"], k=random.randint(1, 3)),
                delivery_timeline_days=random.randint(15, 90),
                location=random.choice(KENYA_COUNTIES),
                status=ListingStatusEnum.active,
                minimum_purchase=rand_float(100, 1000),
                metadata_json={"certification_body": random.choice(["Verra", "Gold Standard"])},
                created_at=days_ago(random.randint(1, 60)),
            )
            db.add(listing)
            listings.append(listing)

    await db.flush()

    # Buyer profiles
    buyer_users = [u for u in users if u.role == UserRoleEnum.viewer]
    for user in buyer_users:
        profile = BuyerProfile(
            user_id=user.id,
            buyer_type=random.choice(list(BuyerTypeEnum)),
            company_name=f"{user.name.split()[0]} Carbon Solutions",
            preferred_methodologies=random.sample(["TPDDTEC_v4", "VM0050", "VMR0006", "AMS-II.G"], k=random.randint(1, 3)),
            price_range_min_usd=rand_float(3, 10),
            price_range_max_usd=rand_float(15, 50),
            preferred_locations=random.sample(KENYA_COUNTIES, k=random.randint(1, 3)),
            delivery_timeline_preference_days=random.randint(30, 180),
            auto_match_enabled=random.choice([True, False]),
        )
        db.add(profile)

    await db.flush()

    # Trade matches
    for listing in listings:
        if not buyer_users:
            break
        buyer = random.choice(buyer_users)
        match = TradeMatch(
            listing_id=listing.id,
            buyer_id=buyer.id,
            match_score=rand_float(0.5, 0.98),
            methodology_match=random.choice([True, False]),
            price_match=random.choice([True, False]),
            location_match=random.choice([True, False]),
            timeline_match=random.choice([True, False]),
            status=random.choice(["suggested", "contacted", "negotiating"]),
        )
        db.add(match)

    await db.flush()

    # Transactions
    for listing in random.sample(listings, min(len(listings), 5)):
        if not buyer_users or not sellers:
            break
        buyer = random.choice(buyer_users)
        seller = random.choice(sellers)
        credits = rand_float(500, min(listing.available_credits, 10000))
        price = listing.price_per_credit_usd
        total = round(credits * price, 2)
        commission = round(total * 0.025, 2)

        tx = BrokerageTransaction(
            listing_id=listing.id,
            buyer_id=buyer.id,
            seller_id=seller.id,
            trade_type=random.choice(list(TradeTypeEnum)),
            credits_amount=credits,
            price_per_credit_usd=price,
            total_value_usd=total,
            commission_rate=0.025,
            commission_usd=commission,
            status=random.choice(list(TransactionStatusEnum)),
            delivery_date=date.today() + timedelta(days=random.randint(15, 90)),
            metadata_json={"negotiation_rounds": random.randint(1, 5)},
            created_at=days_ago(random.randint(1, 30)),
        )
        db.add(tx)
        await db.flush()

        # Escrow
        if tx.status in (TransactionStatusEnum.in_escrow, TransactionStatusEnum.completed):
            escrow = Escrow(
                transaction_id=tx.id,
                amount_usd=total,
                buyer_deposited=random.choice([True, False]),
                seller_transferred=random.choice([True, False]),
                status="holding" if tx.status == TransactionStatusEnum.in_escrow else "released",
                released_at=now() if tx.status == TransactionStatusEnum.completed else None,
            )
            db.add(escrow)

        # Commission
        comm = Commission(
            transaction_id=tx.id,
            amount_usd=commission,
            rate=0.025,
            invoiced=random.choice([True, False]),
            invoice_number=f"INV-{random.randint(1000, 9999)}" if random.choice([True, False]) else None,
            paid_at=days_ago(random.randint(1, 10)) if random.choice([True, False]) else None,
        )
        db.add(comm)

    await db.flush()
    print("✅ Created brokerage data (listings, buyers, transactions, escrow, commissions)")


async def seed_tokenization(
    db: AsyncSession, projects: list[Project], calcs: list[CalculationRun], users: list[User]
) -> None:
    """Create tokenization records."""
    tokenizable_projects = [p for p in projects if p.tokenization_enabled and p.status == ProjectStatusEnum.verified]
    tokens: list[CarbonCreditToken] = []

    for project in tokenizable_projects:
        project_calcs = [c for c in calcs if c.project_id == project.id and c.status == CalculationStatusEnum.approved]
        for calc in project_calcs:
            tonnes = calc.emissions_reduction_tCO2e or rand_float(1000, 50000)
            token = CarbonCreditToken(
                project_id=project.id,
                calculation_run_id=calc.id,
                tonnes_co2e=tonnes,
                vintage_year=random.randint(2020, 2024),
                methodology=project.methodology.value,
                vvb_registry=random.choice(["Verra", "Gold Standard", "CDM"]),
                vvb_certificate_id=f"CERT-{random.randint(100000, 999999)}",
                radix_token_address=None,
                radix_resource_address=None,
                metadata_json={"serial_range": f"{random.randint(1, 1000)}-{random.randint(1001, 5000)}"},
                status=random.choice(list(TokenStatusEnum)),
                is_fractional=random.choice([True, False]),
                created_at=days_ago(random.randint(1, 60)),
            )
            db.add(token)
            tokens.append(token)

    await db.flush()

    # Token listings
    for token in tokens:
        if token.status in (TokenStatusEnum.listed, TokenStatusEnum.sold):
            seller = random.choice(users)
            listing = TokenListing(
                token_id=token.id,
                seller_id=seller.id,
                price_per_tonne_usd=rand_float(5, 30),
                amount_available=token.tonnes_co2e * random.uniform(0.3, 0.9),
                status="active" if token.status == TokenStatusEnum.listed else "sold",
                created_at=days_ago(random.randint(1, 30)),
            )
            db.add(listing)

    await db.flush()

    # Token retirements
    for token in random.sample(tokens, min(len(tokens), 3)):
        retiree = random.choice(users)
        retirement = TokenRetirement(
            token_id=token.id,
            retired_by=retiree.id,
            tonnes_retired=token.tonnes_co2e * random.uniform(0.1, 0.5),
            purpose="Corporate net-zero commitment 2024",
            beneficiary_name=retiree.name,
            beneficiary_location=random.choice(KENYA_COUNTIES),
            retirement_certificate_url=f"https://cert.carbonverify.io/retire/{uuid.uuid4()}",
            created_at=days_ago(random.randint(1, 30)),
        )
        db.add(retirement)

    await db.flush()
    print(f"✅ Created tokenization data ({len(tokens)} tokens, listings, retirements)")


async def seed_corporate_portfolios(db: AsyncSession, users: list[User], tokens: list[CarbonCreditToken]) -> None:
    """Create corporate portfolios and holdings."""
    buyer_users = [u for u in users if u.role == UserRoleEnum.viewer]

    for user in buyer_users:
        portfolio = CorporatePortfolio(
            user_id=user.id,
            total_credits_held=rand_float(0, 50000),
            total_credits_retired=rand_float(0, 10000),
            portfolio_value_usd=rand_float(0, 500000),
            esg_report_config={
                "reporting_framework": "GRI",
                "scope": ["scope1", "scope2", "scope3"],
                "disclosure_level": "detailed",
            },
            created_at=days_ago(random.randint(1, 180)),
        )
        db.add(portfolio)
        await db.flush()

        for token in random.sample(tokens, min(len(tokens), random.randint(1, 4))):
            holding = PortfolioHolding(
                portfolio_id=portfolio.id,
                token_id=token.id,
                tonnes_held=rand_float(100, min(token.tonnes_co2e, 5000)),
                tonnes_retired=rand_float(0, 500),
                acquisition_price_usd=rand_float(5, 25),
                acquired_at=days_ago(random.randint(1, 90)),
            )
            db.add(holding)

    await db.flush()
    print("✅ Created corporate portfolios and holdings")


async def seed_leads(db: AsyncSession, users: list[User]) -> None:
    """Create lead intelligence records."""
    sources = list(LeadRegistrySourceEnum)
    statuses = list(LeadProjectStatusEnum)
    priorities = list(LeadPriorityEnum)
    workflow_statuses = list(LeadWorkflowStatusEnum)

    for i in range(random.randint(15, 30)):
        registry = random.choice(sources)
        lead = Lead(
            registry_source=registry,
            external_id=f"{registry.value}_{random.randint(10000, 99999)}",
            project_name=random.choice([
                f"Cookstove Distribution {random.choice(KENYA_COUNTIES)}",
                f"Forest Conservation Zone {random.randint(1, 20)}",
                f"Mangrove Restoration {random.choice(KENYA_COUNTIES)}",
                f"Solar Home System {random.randint(1, 50)}",
                f"Biogas Digester Programme {random.choice(KENYA_COUNTIES)}",
            ]),
            project_developer=random.choice(["EcoDev Corp", "GreenAfrica Ltd", "CarbonPartners", None]),
            developer_contact="contact@example.com" if random.random() > 0.5 else None,
            developer_email="dev@example.com" if random.random() > 0.5 else None,
            country="Kenya",
            region=random.choice(KENYA_COUNTIES),
            location_coords=f"{random.uniform(-4, 4):.4f},{random.uniform(34, 42):.4f}",
            methodology=random.choice(["VMR0006", "VM0050", "AMS-II.G", "TPDDTEC_v4"]),
            sector=random.choice(["cookstoves", "forestry", "renewable_energy", "agriculture"]),
            status=random.choice(statuses),
            crediting_period_start=rand_date(date(2018, 1, 1), date(2023, 1, 1)),
            crediting_period_end=rand_date(date(2023, 1, 1), date(2030, 1, 1)),
            last_verification_date=rand_date(date(2020, 1, 1), date(2024, 1, 1)) if random.random() > 0.3 else None,
            last_monitoring_period_end=rand_date(date(2020, 1, 1), date(2024, 6, 1)) if random.random() > 0.3 else None,
            estimated_credits_per_year=rand_float(1000, 50000),
            registry_url=f"https://registry.example.com/project/{random.randint(1000, 9999)}",
            days_in_status=random.randint(1, 365),
            stuck_score=rand_float(0, 1),
            priority=random.choice(priorities),
            lead_status=random.choice(workflow_statuses),
            notes="High potential project in underserved region" if random.random() > 0.5 else None,
            scraped_at=days_ago(random.randint(1, 30)),
            assigned_to=random.choice(users).id if random.random() > 0.5 else None,
        )
        db.add(lead)

    await db.flush()
    print("✅ Created lead intelligence records")


async def seed_methodology_versions(db: AsyncSession, users: list[User]) -> None:
    """Create methodology version records."""
    methodologies = ["TPDDTEC_v4", "VM0050", "VMR0006", "AMS-II.G"]

    for meth in methodologies:
        for version in ["1.0", "1.1", "2.0"]:
            mv = MethodologyVersion(
                methodology_name=meth,
                version=version,
                effective_date=rand_date(date(2018, 1, 1), date(2024, 1, 1)),
                rules_json={
                    "leakage_default_pct": 5.0,
                    "uncertainty_max": 0.25,
                    "baseline_years": 3,
                },
                change_summary=f"Updated uncertainty thresholds and baseline requirements in version {version}",
                approved_by=random.choice(users).id if random.random() > 0.3 else None,
                is_current=(version == "2.0"),
                created_at=days_ago(random.randint(1, 365)),
            )
            db.add(mv)

    await db.flush()
    print("✅ Created methodology versions")


async def seed_file_uploads(db: AsyncSession, projects: list[Project]) -> None:
    """Create file upload records."""
    for project in projects:
        for _ in range(random.randint(1, 4)):
            ftype = random.choice(list(DetectedFileTypeEnum))
            upload = FileUpload(
                project_id=project.id,
                original_filename=f"upload_{random.randint(1000, 9999)}.{ftype.value}",
                detected_type=ftype,
                mime_type=random.choice(["application/pdf", "text/csv", "image/jpeg", "application/vnd.ms-excel"]),
                s3_key=f"uploads/{project.id}/{uuid.uuid4()}",
                s3_bucket="carbonverify-uploads",
                file_size_bytes=random.randint(1024, 50 * 1024 * 1024),
                file_hash_sha256="a" * 64,
                status=random.choice(list(FileUploadStatusEnum)),
                processing_result={"extracted_rows": random.randint(10, 5000)} if random.random() > 0.5 else None,
                confidence_score=rand_float(0.7, 0.99),
                provenance={"uploader": "demo_seed", "batch_id": f"batch_{random.randint(1, 100)}"},
                created_at=days_ago(random.randint(1, 90)),
            )
            db.add(upload)

    await db.flush()
    print("✅ Created file upload records")


async def seed_methodology_templates(db: AsyncSession) -> None:
    result = await db.execute(select(MethodologyTemplate).limit(1))
    if result.scalar_one_or_none():
        return

    templates = [
        MethodologyTemplate(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            name="Cookstoves / Household Energy",
            sector="Cookstoves",
            is_active=True,
            description="Improved biomass cookstoves distributed to households to reduce fuel use and emissions.",
            defaults_json={
                "boundaries": {
                    "geographic_scope": "Rural households in target region",
                    "temporal_scope": "2025-01-01 to 2034-12-31",
                    "physical_boundary": "Households receiving improved cookstoves and their fuel consumption",
                    "ghg_sources_included": "CO₂ and CH₄ from avoided biomass fuel combustion",
                },
                "data_sources": [
                    {
                        "source_type": "household_survey",
                        "description": "Survey of stove usage and fuel consumption",
                        "frequency": "annual",
                        "provider_quality": "Third-party enumerator with 10% spot checks",
                    }
                ],
            },
        ),
        MethodologyTemplate(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            name="Blue Carbon / Coastal Ecosystems",
            sector="Blue Carbon",
            is_active=True,
            description="Mangrove, seagrass, or tidal marsh restoration and conservation for carbon sequestration.",
            defaults_json={
                "boundaries": {
                    "geographic_scope": "Coastal project area",
                    "temporal_scope": "2025-01-01 to 2054-12-31",
                    "physical_boundary": "Restored and conserved mangrove/seagrass area",
                    "ghg_sources_included": "CO₂ sequestered in coastal ecosystem biomass and soils",
                },
                "data_sources": [
                    {
                        "source_type": "satellite_imagery",
                        "description": "Remote sensing of vegetation extent and biomass",
                        "frequency": "annual",
                        "provider_quality": "Public satellite data, validated with field surveys",
                    }
                ],
            },
        ),
    ]
    db.add_all(templates)
    await db.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Main runner
# ──────────────────────────────────────────────────────────────────────────────


async def seed_all() -> None:
    async with AsyncSessionLocal() as db:
        print("🌱 Seeding CarbonVerify demo data...\n")

        users = await seed_users(db)
        developers = await seed_developers(db, users)
        projects = await seed_projects(db, developers)
        sources = await seed_data_sources(db, projects)
        calcs = await seed_calculations(db, projects, users)
        reports = await seed_reports(db, projects, calcs)
        queue = await seed_review_queue(db, projects, calcs, reports, users)
        agents = await seed_agent_runs(db, projects)
        await seed_orchestrator_events(db, projects, agents)
        await seed_audit_logs(db, users, projects)
        await seed_compliance(db, projects, users)
        await seed_brokerage(db, projects, users, calcs)
        await seed_tokenization(db, projects, calcs, users)

        # Get tokens for portfolio seeding
        from app.models import CarbonCreditToken as TokenModel
        result = await db.execute(select(TokenModel))
        tokens = result.scalars().all()

        await seed_corporate_portfolios(db, users, tokens)
        await seed_leads(db, users)
        await seed_methodology_templates(db)
        await seed_methodology_versions(db, users)
        await seed_file_uploads(db, projects)
        await seed_field_data(db, projects, users)
        await seed_human_escalations(db, projects, users)
        await seed_admin_portfolio(db, users, tokens)

        await db.commit()
        print("\n🎉 Demo data seeded successfully!")
        print(f"\n📋 You can log in with any of these accounts:")
        print(f"   Password for all: {DEMO_PASSWORD}")
        for u in users:
            print(f"   • {u.email}  ({u.role.value})")


async def seed_field_data(db: AsyncSession, projects: list[Project], users: list[User]) -> None:
    """Create enumerators, survey responses, and support tickets for the Field dashboard."""
    field_projects = [p for p in projects if p.status in (ProjectStatusEnum.data_collection, ProjectStatusEnum.monitoring, ProjectStatusEnum.verified)]
    if not field_projects:
        field_projects = projects[:2]

    enumerators: list[Enumerator] = []
    for i in range(random.randint(5, 10)):
        enum = Enumerator(
            project_id=random.choice(field_projects).id,
            name=random.choice([
                "Grace Ochieng", "Peter Kamau", "Wanjiru Mwangi", "Otieno Onyango",
                "Achieng Akinyi", "Kipchoge Kiprotich", "Nafula Wafula", "Mutua Musyoka",
                "Amina Hassan", "Juma Abdallah",
            ]),
            phone_number=f"+2547{random.randint(10, 99)}{random.randint(100000, 999999)}",
            language_preference=random.choice(["en", "sw", "luo", "kik"]),
            active=random.choice([True, True, True, False]),
            data_quality_score=rand_float(0.70, 0.98),
            submissions_count=random.randint(20, 500),
            rejections_count=random.randint(0, 30),
            last_sync_at=days_ago(random.randint(0, 3)),
            created_at=days_ago(random.randint(10, 180)),
        )
        db.add(enum)
        enumerators.append(enum)

    await db.flush()

    # Create WhatsApp conversations needed for survey_responses and support_tickets
    conversations: list[WhatsAppConversation] = []
    for enum in enumerators:
        conv = WhatsAppConversation(
            project_id=enum.project_id,
            phone_number=enum.phone_number,
            flow_type=random.choice(list(ConversationFlowEnum)),
            state=random.choice(list(ConversationStateEnum)),
            assigned_enumerator_id=enum.id,
            created_at=days_ago(random.randint(0, 7)),
        )
        db.add(conv)
        conversations.append(conv)

    await db.flush()

    surveys: list[SurveyResponse] = []
    for enum in enumerators:
        conv = next((c for c in conversations if c.assigned_enumerator_id == enum.id), None)
        for _ in range(random.randint(3, 15)):
            survey = SurveyResponse(
                project_id=enum.project_id,
                conversation_id=conv.id if conv else random.choice(conversations).id,
                enumerator_id=enum.id,
                household_id=f"HH-{random.randint(1000, 9999)}",
                stove_id=f"STV-{random.randint(100, 999)}",
                village_name=random.choice(VILLAGES),
                gps_latitude=random.uniform(-4.5, 1.5),
                gps_longitude=random.uniform(34.0, 42.0),
                validation_status=random.choice(list(ValidationStatusEnum)),
                confidence_score=rand_float(0.6, 0.99),
                submitted_via=random.choice(["whatsapp", "mobile_app", "sms"]),
                created_at=days_ago(random.randint(0, 7)),
            )
            db.add(survey)
            surveys.append(survey)

    await db.flush()

    tickets: list[SupportTicket] = []
    for _ in range(random.randint(3, 8)):
        ticket = SupportTicket(
            project_id=random.choice(field_projects).id,
            conversation_id=random.choice(conversations).id,
            phone_number=f"+2547{random.randint(10, 99)}{random.randint(100000, 999999)}",
            issue_type=random.choice(["stove_broken", "cant_sync", "wrong_data", "other"]),
            description=random.choice([
                "Enumerator cannot submit surveys — sync stuck at 98%",
                "GPS coordinates showing wrong village",
                "Photos not uploading on slow connection",
                "App crashing after latest update",
                "Enumerator forgot PIN and cannot login",
            ]),
            status=random.choice(["open", "open", "resolved"]),
            assigned_to=random.choice(users).id if random.random() > 0.5 else None,
            created_at=days_ago(random.randint(0, 14)),
        )
        db.add(ticket)
        tickets.append(ticket)

    await db.flush()
    print(f"✅ Created field data ({len(enumerators)} enumerators, {len(surveys)} surveys, {len(tickets)} tickets)")


async def seed_human_escalations(db: AsyncSession, projects: list[Project], users: list[User]) -> None:
    """Create human escalation records for the VVB Pipeline."""
    from app.validation_engine.models import (
        HumanEscalation, EscalationLevel, EscalationStatus,
        ValidationRun, ValidationWorkflow, WorkflowRunStatus,
    )

    # Create a dummy validation workflow
    workflow = ValidationWorkflow(
        name="Demo Validation Workflow",
        version="1.0.0",
        description="Auto-generated workflow for demo escalations",
        active=True,
        workflow_graph={"steps": []},
        graph_hash="a" * 64,
        sla_seconds=3600,
        human_gates_required=True,
        created_at=days_ago(random.randint(30, 180)),
    )
    db.add(workflow)
    await db.flush()

    # Create some validation runs
    runs: list[ValidationRun] = []
    for _ in range(random.randint(6, 12)):
        run = ValidationRun(
            workflow_id=workflow.id,
            project_id=random.choice(projects).id if projects else None,
            triggered_by=random.choice(users).id if users else None,
            trigger_event=random.choice(["data_uploaded", "calculation_completed", "report_submitted", "vvb_feedback"]),
            status=random.choice(list(WorkflowRunStatus)),
            input_data={},
            output_data={},
            created_at=days_ago(random.randint(1, 30)),
        )
        db.add(run)
        runs.append(run)

    await db.flush()

    reasons = [
        "VVB requested clarification on baseline fuel consumption methodology",
        "Missing GPS boundary documentation for monitoring period 2024-Q1",
        "Confidence score below threshold (0.72) for calculation step 3",
        "Duplicate household IDs detected in survey batch 2024-03",
        "Leakage assessment exceeds 8% threshold — operator review required",
        "Photo evidence quality insufficient for 12 surveyed households",
        "MRV data gap: IoT sensor offline for 14 days in Kajiado region",
        "VVB feedback: Provide additional KPT results for stove adoption verification",
    ]

    escalations: list[HumanEscalation] = []
    for i in range(random.randint(6, 12)):
        status = random.choice(list(EscalationStatus))
        acknowledged_at = days_ago(random.randint(1, 5)) if status in (EscalationStatus.acknowledged, EscalationStatus.resolved, EscalationStatus.timed_out) else None
        resolved_at = days_ago(random.randint(0, 3)) if status == EscalationStatus.resolved else None

        esc = HumanEscalation(
            run_id=random.choice(runs).id,
            escalation_reason=random.choice(reasons),
            severity_score=rand_float(0.3, 0.95),
            level=random.choice(list(EscalationLevel)),
            status=status,
            assigned_to=random.choice(users).id if status != EscalationStatus.pending else None,
            human_decision="approved_with_conditions" if status == EscalationStatus.resolved else None,
            human_notes="Reviewed and approved after additional documentation provided." if status == EscalationStatus.resolved else None,
            sla_deadline=now() + timedelta(days=random.randint(3, 14)),
            acknowledged_at=acknowledged_at,
            resolved_at=resolved_at,
            created_at=days_ago(random.randint(1, 10)),
        )
        db.add(esc)
        escalations.append(esc)

    await db.flush()
    print(f"✅ Created {len(escalations)} human escalations")


async def seed_admin_portfolio(db: AsyncSession, users: list[User], tokens: list[CarbonCreditToken]) -> None:
    """Ensure the admin user has portfolio holdings so the Corporate Dashboard shows data."""
    admin = next((u for u in users if u.role == UserRoleEnum.admin), None)
    if not admin or not tokens:
        return

    portfolio_result = await db.execute(
        select(CorporatePortfolio).where(CorporatePortfolio.user_id == admin.id)
    )
    portfolio = portfolio_result.scalar_one_or_none()

    if not portfolio:
        portfolio = CorporatePortfolio(
            user_id=admin.id,
            total_credits_held=0.0,
            total_credits_retired=0.0,
            portfolio_value_usd=0.0,
            created_at=days_ago(random.randint(30, 180)),
        )
        db.add(portfolio)
        await db.flush()

    for token in random.sample(tokens, min(len(tokens), random.randint(2, 4))):
        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            token_id=token.id,
            tonnes_held=rand_float(500, min(token.tonnes_co2e, 8000)),
            tonnes_retired=rand_float(0, 300),
            acquisition_price_usd=rand_float(5, 25),
            acquired_at=days_ago(random.randint(1, 90)),
        )
        db.add(holding)
        portfolio.total_credits_held += holding.tonnes_held
        portfolio.portfolio_value_usd += holding.tonnes_held * holding.acquisition_price_usd

    await db.flush()
    print("✅ Seeded admin portfolio holdings")


if __name__ == "__main__":
    asyncio.run(seed_all())
