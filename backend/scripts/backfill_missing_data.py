"""Backfill missing demo data for features that are currently empty."""

import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ENVIRONMENT", "development")

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import (
    CarbonCreditToken,
    CorporatePortfolio,
    Enumerator,
    PortfolioHolding,
    Project,
    SupportTicket,
    SurveyResponse,
    User,
    UserRoleEnum,
    ValidationStatusEnum,
    WhatsAppConversation,
    ConversationFlowEnum,
    ConversationStateEnum,
)
from app.validation_engine.models import HumanEscalation, EscalationLevel, EscalationStatus


def now() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return now() - timedelta(days=n)


def rand_float(min_val: float, max_val: float, decimals: int = 2) -> float:
    return round(random.uniform(min_val, max_val), decimals)


VILLAGES = [
    "Kibera", "Mathare", "Kawangware", "Dagoretti", "Embakasi",
    "Ruiru", "Thika", "Karatina", "Othaya", "Mweiga", "Nanyuki",
    "Isiolo", "Marsabit", "Moyale", "Mandera", "Wajir", "Garissa",
]


async def seed_field_data(db: AsyncSession) -> None:
    """Create enumerators, surveys, and support tickets if missing."""
    existing = await db.scalar(select(func.count(Enumerator.id)))
    if existing > 0:
        print(f"⏭️  Skipping field data — {existing} enumerators already exist")
        return

    projects_result = await db.execute(select(Project))
    projects = list(projects_result.scalars().all())
    users_result = await db.execute(select(User))
    users = list(users_result.scalars().all())

    field_projects = projects[:3] if projects else []

    enumerators = []
    for i in range(random.randint(5, 10)):
        enum = Enumerator(
            project_id=random.choice(field_projects).id if field_projects else None,
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

    # Create dummy WhatsApp conversations first (needed for surveys and tickets)
    conversations = []
    for _ in range(random.randint(10, 20)):
        conv = WhatsAppConversation(
            project_id=random.choice(field_projects).id if field_projects else None,
            phone_number=f"+2547{random.randint(10, 99)}{random.randint(100000, 999999)}",
            flow_type=random.choice(list(ConversationFlowEnum)),
            state=random.choice(list(ConversationStateEnum)),
            language=random.choice(["en", "sw"]),
            created_at=days_ago(random.randint(0, 30)),
        )
        db.add(conv)
        conversations.append(conv)
    await db.flush()

    for enum in enumerators:
        for _ in range(random.randint(3, 15)):
            survey = SurveyResponse(
                project_id=enum.project_id,
                conversation_id=random.choice(conversations).id if conversations else None,
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

    for _ in range(random.randint(3, 8)):
        ticket = SupportTicket(
            project_id=random.choice(field_projects).id if field_projects else None,
            conversation_id=random.choice(conversations).id if conversations else None,
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
            assigned_to=random.choice(users).id if users and random.random() > 0.5 else None,
            created_at=days_ago(random.randint(0, 14)),
        )
        db.add(ticket)

    await db.flush()
    print("✅ Created field data")


async def seed_human_escalations(db: AsyncSession) -> None:
    """Create human escalations if missing."""
    existing = await db.scalar(select(func.count(HumanEscalation.id)))
    if existing > 0:
        print(f"⏭️  Skipping escalations — {existing} already exist")
        return

    users_result = await db.execute(select(User))
    users = list(users_result.scalars().all())

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

    for i in range(random.randint(6, 12)):
        status = random.choice(list(EscalationStatus))
        acknowledged_at = days_ago(random.randint(1, 5)) if status in (EscalationStatus.acknowledged, EscalationStatus.resolved, EscalationStatus.timed_out) else None
        resolved_at = days_ago(random.randint(0, 3)) if status == EscalationStatus.resolved else None

        esc = HumanEscalation(
            run_id=uuid.uuid4(),
            escalation_reason=random.choice(reasons),
            severity_score=rand_float(0.3, 0.95),
            level=random.choice([EscalationLevel.low, EscalationLevel.medium, EscalationLevel.high, EscalationLevel.critical]),
            status=status,
            assigned_to=random.choice(users).id if users and status != EscalationStatus.pending else None,
            human_decision="approved_with_conditions" if status == EscalationStatus.resolved else None,
            human_notes="Reviewed and approved after additional documentation provided." if status == EscalationStatus.resolved else None,
            sla_deadline=now() + timedelta(days=random.randint(3, 14)),
            acknowledged_at=acknowledged_at,
            resolved_at=resolved_at,
            created_at=days_ago(random.randint(1, 10)),
        )
        db.add(esc)

    await db.flush()
    print("✅ Created human escalations")


async def seed_admin_portfolio(db: AsyncSession) -> None:
    """Ensure admin user has portfolio holdings."""
    admin_result = await db.execute(select(User).where(User.role == UserRoleEnum.admin).limit(1))
    admin = admin_result.scalar_one_or_none()
    if not admin:
        print("⏭️  No admin user found")
        return

    tokens_result = await db.execute(select(CarbonCreditToken))
    tokens = list(tokens_result.scalars().all())
    if not tokens:
        print("⏭️  No tokens available for portfolio")
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

    existing_holdings = await db.scalar(
        select(func.count(PortfolioHolding.id)).where(PortfolioHolding.portfolio_id == portfolio.id)
    )
    if existing_holdings > 0:
        print(f"⏭️  Admin already has {existing_holdings} holdings")
        return

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


async def backfill_all() -> None:
    async with AsyncSessionLocal() as db:
        print("🔧 Backfilling missing demo data...\n")
        await seed_field_data(db)
        await seed_human_escalations(db)
        await seed_admin_portfolio(db)
        await db.commit()
        print("\n🎉 Backfill complete!")


if __name__ == "__main__":
    asyncio.run(backfill_all())
