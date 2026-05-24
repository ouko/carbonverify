import uuid
import pytest

from app.brokerage.matching_engine import MatchingEngine, _score_methodology, _score_price, _score_location, _score_timeline
from app.models import BrokerageListing, BuyerProfile, ListingStatusEnum, BuyerTypeEnum


class TestMatchingScoring:
    def test_score_methodology_match(self):
        assert _score_methodology("TPDDTEC_v4", ["TPDDTEC_v4", "VM0050"]) is True

    def test_score_methodology_no_preference(self):
        assert _score_methodology("TPDDTEC_v4", []) is True

    def test_score_methodology_mismatch(self):
        assert _score_methodology("TPDDTEC_v4", ["VM0050"]) is False

    def test_score_price_within_range(self):
        assert _score_price(15.0, 10.0, 20.0) is True

    def test_score_price_above_max(self):
        assert _score_price(25.0, 10.0, 20.0) is False

    def test_score_price_below_min(self):
        assert _score_price(5.0, 10.0, 20.0) is False

    def test_score_price_no_range(self):
        assert _score_price(100.0, None, None) is True

    def test_score_location_match(self):
        assert _score_location("Kenya", ["Kenya", "Ghana"]) is True

    def test_score_location_no_preference(self):
        assert _score_location("Kenya", []) is True

    def test_score_location_none(self):
        assert _score_location(None, ["Kenya"]) is False

    def test_score_timeline_within(self):
        assert _score_timeline(30, 30) is True

    def test_score_timeline_over_tolerance(self):
        assert _score_timeline(50, 30) is False

    def test_score_timeline_within_tolerance(self):
        assert _score_timeline(40, 30) is True


class TestMatchingEngine:
    @pytest.mark.asyncio
    async def test_find_matches_for_listing(self, client, db_session):
        listing = BrokerageListing(
            project_id=uuid.uuid4(),
            seller_id=uuid.uuid4(),
            available_credits=10000,
            price_per_credit_usd=15.0,
            vintage_year=2024,
            methodology="TPDDTEC_v4",
            delivery_timeline_days=30,
            location="Kenya",
            status=ListingStatusEnum.active,
        )
        db_session.add(listing)

        buyer = BuyerProfile(
            user_id=uuid.uuid4(),
            buyer_type=BuyerTypeEnum.corporate,
            preferred_methodologies=["TPDDTEC_v4"],
            price_range_min_usd=10.0,
            price_range_max_usd=20.0,
            preferred_locations=["Kenya"],
            delivery_timeline_preference_days=45,
            auto_match_enabled=True,
        )
        db_session.add(buyer)
        await db_session.commit()

        engine = MatchingEngine(db_session)
        matches = await engine.find_matches_for_listing(listing.id)
        assert len(matches) > 0
        assert matches[0].score >= 0.6
        assert matches[0].methodology_match is True
        assert matches[0].price_match is True

    @pytest.mark.asyncio
    async def test_find_matches_for_buyer(self, client, db_session):
        buyer = BuyerProfile(
            user_id=uuid.uuid4(),
            buyer_type=BuyerTypeEnum.corporate,
            preferred_methodologies=["VM0050"],
            price_range_min_usd=15.0,
            price_range_max_usd=25.0,
            auto_match_enabled=True,
        )
        db_session.add(buyer)

        listing = BrokerageListing(
            project_id=uuid.uuid4(),
            seller_id=uuid.uuid4(),
            available_credits=5000,
            price_per_credit_usd=18.0,
            vintage_year=2024,
            methodology="VM0050",
            delivery_timeline_days=30,
            status=ListingStatusEnum.active,
        )
        db_session.add(listing)
        await db_session.commit()

        engine = MatchingEngine(db_session)
        matches = await engine.find_matches_for_buyer(buyer.user_id)
        assert len(matches) > 0
        assert matches[0].score >= 0.6
