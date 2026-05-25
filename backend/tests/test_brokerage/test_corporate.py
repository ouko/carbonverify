import uuid
import pytest
from datetime import date

from app.brokerage.corporate_service import CorporateService
from app.models import CarbonCreditToken


class TestCorporateService:
    @pytest.mark.asyncio
    async def test_get_or_create_portfolio(self, client, db_session):
        service = CorporateService(db_session)
        user_id = uuid.uuid4()
        portfolio = await service.get_or_create_portfolio(user_id)
        assert portfolio.user_id == user_id
        assert portfolio.total_credits_held == 0.0

        # Second call should return same portfolio
        portfolio2 = await service.get_or_create_portfolio(user_id)
        assert portfolio2.id == portfolio.id

    @pytest.mark.asyncio
    async def test_add_holding_and_summary(self, client, db_session):
        service = CorporateService(db_session)
        user_id = uuid.uuid4()

        # Create token
        token = CarbonCreditToken(
            project_id=uuid.uuid4(),
            calculation_run_id=uuid.uuid4(),
            tonnes_co2e=5000.0,
            vintage_year=2024,
            methodology="TPDDTEC_v4",
            vvb_registry="Verra",
            status="minted",
        )
        db_session.add(token)
        await db_session.commit()
        await db_session.refresh(token)

        # Add holding
        holding = await service.add_holding(user_id, token.id, 1000.0, 12.50)
        assert holding.tonnes_held == 1000.0
        assert holding.acquisition_price_usd == 12.50

        # Check portfolio summary
        summary = await service.get_portfolio_summary(user_id)
        assert summary["total_credits_held"] == 1000.0
        assert summary["portfolio_value_usd"] == 12500.0
        assert summary["holdings_count"] == 1

    @pytest.mark.asyncio
    async def test_generate_esg_report(self, client, db_session):
        service = CorporateService(db_session)
        user_id = uuid.uuid4()

        # Create and add holdings
        token1 = CarbonCreditToken(
            project_id=uuid.uuid4(),
            calculation_run_id=uuid.uuid4(),
            tonnes_co2e=5000.0,
            vintage_year=2024,
            methodology="TPDDTEC_v4",
            vvb_registry="Verra",
            status="minted",
        )
        db_session.add(token1)
        await db_session.commit()
        await db_session.refresh(token1)

        await service.add_holding(user_id, token1.id, 1000.0, 12.50)

        from datetime import datetime as dt
        report = await service.generate_esg_report(
            user_id=user_id,
            company_name="Acme Corp",
            reporting_period_start=date(2000, 1, 1),
            reporting_period_end=date(dt.now().year + 1, 12, 31),
            scope="Scope 3",
            sdgs=["SDG 7", "SDG 13"],
        )
        assert report["company_name"] == "Acme Corp"
        assert report["scope"] == "Scope 3"
        assert report["total_offsets_tco2e"] == 1000.0
        assert "SDG 7" in report["sdg_impact_summary"]
        assert "SDG 13" in report["sdg_impact_summary"]
        assert "report_id" in report
