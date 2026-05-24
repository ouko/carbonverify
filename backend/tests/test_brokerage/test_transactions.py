import uuid
import pytest
import pytest_asyncio
from datetime import date, timedelta

from app.brokerage.transaction_engine import TransactionEngine
from app.models import BrokerageListing, BrokerageTransaction, Escrow, Commission, ListingStatusEnum, TradeTypeEnum


class TestTransactionEngine:
    @pytest_asyncio.fixture
    async def active_listing(self, db_session):
        listing = BrokerageListing(
            project_id=uuid.uuid4(),
            seller_id=uuid.uuid4(),
            available_credits=10000,
            price_per_credit_usd=15.0,
            vintage_year=2024,
            methodology="TPDDTEC_v4",
            delivery_timeline_days=30,
            status=ListingStatusEnum.active,
            minimum_purchase=100,
        )
        db_session.add(listing)
        await db_session.commit()
        await db_session.refresh(listing)
        return listing

    @pytest.mark.asyncio
    async def test_create_spot_transaction(self, client, db_session, active_listing):
        engine = TransactionEngine(db_session)
        buyer_id = uuid.uuid4()
        tx = await engine.create_transaction(
            listing_id=active_listing.id,
            buyer_id=buyer_id,
            credits_amount=1000,
            trade_type=TradeTypeEnum.spot,
        )
        assert tx.trade_type == TradeTypeEnum.spot
        assert tx.total_value_usd == 15000.0
        assert tx.commission_usd == 375.0  # 2.5%
        assert tx.status.value == "pending"

    @pytest.mark.asyncio
    async def test_create_forward_transaction(self, client, db_session, active_listing):
        engine = TransactionEngine(db_session)
        buyer_id = uuid.uuid4()
        delivery = date.today() + timedelta(days=60)
        tx = await engine.create_transaction(
            listing_id=active_listing.id,
            buyer_id=buyer_id,
            credits_amount=500,
            trade_type=TradeTypeEnum.forward,
            delivery_date=delivery,
        )
        assert tx.trade_type == TradeTypeEnum.forward
        assert tx.delivery_date == delivery

    @pytest.mark.asyncio
    async def test_create_escrow_transaction(self, client, db_session, active_listing):
        engine = TransactionEngine(db_session)
        buyer_id = uuid.uuid4()
        tx = await engine.create_transaction(
            listing_id=active_listing.id,
            buyer_id=buyer_id,
            credits_amount=200,
            trade_type=TradeTypeEnum.escrow,
        )
        assert tx.trade_type == TradeTypeEnum.escrow

        # Check escrow was created
        escrow_result = await db_session.execute(
            __import__("sqlalchemy").select(Escrow).where(Escrow.transaction_id == tx.id)
        )
        escrow = escrow_result.scalar_one_or_none()
        assert escrow is not None
        assert escrow.amount_usd == 3000.0

    @pytest.mark.asyncio
    async def test_insufficient_credits(self, client, db_session, active_listing):
        engine = TransactionEngine(db_session)
        buyer_id = uuid.uuid4()
        with pytest.raises(ValueError, match="Insufficient credits"):
            await engine.create_transaction(
                listing_id=active_listing.id,
                buyer_id=buyer_id,
                credits_amount=50000,
                trade_type=TradeTypeEnum.spot,
            )

    @pytest.mark.asyncio
    async def test_cancel_transaction_restores_credits(self, client, db_session, active_listing):
        engine = TransactionEngine(db_session)
        buyer_id = uuid.uuid4()
        tx = await engine.create_transaction(
            listing_id=active_listing.id,
            buyer_id=buyer_id,
            credits_amount=1000,
            trade_type=TradeTypeEnum.spot,
        )

        await engine.cancel_transaction(tx.id, "Buyer changed mind")

        # Check credits restored
        result = await db_session.execute(
            __import__("sqlalchemy").select(BrokerageListing).where(BrokerageListing.id == active_listing.id)
        )
        listing = result.scalar_one()
        assert listing.available_credits == 10000
        assert listing.status == ListingStatusEnum.active

    @pytest.mark.asyncio
    async def test_confirm_and_execute_spot(self, client, db_session, active_listing):
        engine = TransactionEngine(db_session)
        buyer_id = uuid.uuid4()
        tx = await engine.create_transaction(
            listing_id=active_listing.id,
            buyer_id=buyer_id,
            credits_amount=500,
            trade_type=TradeTypeEnum.spot,
        )

        tx = await engine.confirm_transaction(tx.id)
        assert tx.status.value == "confirmed"

        tx = await engine.execute_spot_trade(tx.id)
        assert tx.status.value == "completed"
