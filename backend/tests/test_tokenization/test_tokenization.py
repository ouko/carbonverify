import uuid
import pytest
import pytest_asyncio

from app.tokenization.token_service import TokenizationService
from app.models import CarbonCreditToken, TokenStatusEnum, CalculationRun


class TestTokenization:
    @pytest_asyncio.fixture
    async def calc_run(self, db_session):
        calc = CalculationRun(
            project_id=uuid.uuid4(),
            monitoring_period_start=__import__("datetime").date(2024, 1, 1),
            monitoring_period_end=__import__("datetime").date(2024, 6, 30),
            fNRB_value=0.42,
            emissions_reduction_tCO2e=15000.0,
            status="approved",
        )
        db_session.add(calc)
        await db_session.commit()
        await db_session.refresh(calc)
        return calc

    @pytest.mark.asyncio
    async def test_mint_token(self, client, db_session, calc_run):
        service = TokenizationService(db_session)
        token = await service.mint_token(
            project_id=calc_run.project_id,
            calculation_run_id=calc_run.id,
            tonnes_co2e=5000.0,
            vintage_year=2024,
            methodology="TPDDTEC_v4",
            vvb_registry="Verra",
            vvb_certificate_id="VCU-1234",
        )
        assert token.tonnes_co2e == 5000.0
        assert token.status == TokenStatusEnum.minted
        assert token.radix_token_address is not None
        assert token.vvb_certificate_id == "VCU-1234"

    @pytest.mark.asyncio
    async def test_fractionalize_token(self, client, db_session, calc_run):
        service = TokenizationService(db_session)
        parent = await service.mint_token(
            project_id=calc_run.project_id,
            calculation_run_id=calc_run.id,
            tonnes_co2e=1000.0,
            vintage_year=2024,
            methodology="TPDDTEC_v4",
            vvb_registry="Verra",
        )

        children = await service.fractionalize_token(parent.id, [200.0, 300.0, 500.0])
        assert len(children) == 3
        assert children[0].tonnes_co2e == 200.0
        assert children[0].is_fractional is True
        assert children[0].parent_token_id == parent.id

        # Parent should be marked fractional
        result = await db_session.execute(
            __import__("sqlalchemy").select(CarbonCreditToken).where(CarbonCreditToken.id == parent.id)
        )
        updated_parent = result.scalar_one()
        assert updated_parent.status == TokenStatusEnum.fractional

    @pytest.mark.asyncio
    async def test_fractionalize_wrong_sum(self, client, db_session, calc_run):
        service = TokenizationService(db_session)
        parent = await service.mint_token(
            project_id=calc_run.project_id,
            calculation_run_id=calc_run.id,
            tonnes_co2e=1000.0,
            vintage_year=2024,
            methodology="TPDDTEC_v4",
            vvb_registry="Verra",
        )

        with pytest.raises(ValueError, match="Fractions must sum to"):
            await service.fractionalize_token(parent.id, [200.0, 300.0])

    @pytest.mark.asyncio
    async def test_list_and_buy_token(self, client, db_session, calc_run):
        service = TokenizationService(db_session)
        token = await service.mint_token(
            project_id=calc_run.project_id,
            calculation_run_id=calc_run.id,
            tonnes_co2e=5000.0,
            vintage_year=2024,
            methodology="TPDDTEC_v4",
            vvb_registry="Verra",
        )

        listing = await service.list_token(token.id, uuid.uuid4(), 12.50, 3000.0)
        assert listing.price_per_tonne_usd == 12.50
        assert listing.amount_available == 3000.0

        result = await service.buy_token(listing.id, uuid.uuid4(), 1000.0)
        assert result["tonnes_purchased"] == 1000.0
        assert result["total_cost_usd"] == 12500.0
        assert result["remaining_available"] == 2000.0

    @pytest.mark.asyncio
    async def test_retire_token(self, client, db_session, calc_run):
        service = TokenizationService(db_session)
        token = await service.mint_token(
            project_id=calc_run.project_id,
            calculation_run_id=calc_run.id,
            tonnes_co2e=5000.0,
            vintage_year=2024,
            methodology="TPDDTEC_v4",
            vvb_registry="Verra",
        )

        retirement = await service.retire_token(
            token_id=token.id,
            retired_by=uuid.uuid4(),
            tonnes_retired=2500.0,
            purpose="Scope 3 offset",
            beneficiary_name="Acme Corp",
        )
        assert retirement.tonnes_retired == 2500.0
        assert retirement.beneficiary_name == "Acme Corp"
        assert retirement.radix_burn_tx_ref is not None

        # Token should be retired
        result = await db_session.execute(
            __import__("sqlalchemy").select(CarbonCreditToken).where(CarbonCreditToken.id == token.id)
        )
        updated_token = result.scalar_one()
        assert updated_token.status == TokenStatusEnum.retired
