"""
Buyer-seller matching engine for CarbonVerify brokerage.

Matches listings to buyer profiles based on:
- Methodology preference
- Price range overlap
- Delivery timeline compatibility
- Location preference

Scores range from 0.0 to 1.0. Matches ≥0.6 are considered viable.
"""

import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import BrokerageListing, BuyerProfile, TradeMatch
from app.core.logging import get_logger

logger = get_logger(__name__)

MATCH_THRESHOLD = 0.6


@dataclass
class MatchResult:
    listing_id: uuid.UUID
    buyer_id: uuid.UUID
    score: float
    methodology_match: bool
    price_match: bool
    location_match: bool
    timeline_match: bool


def _score_methodology(listing_methodology: str, buyer_preferences: List[str]) -> bool:
    """Check if listing methodology is in buyer's preferred list."""
    if not buyer_preferences:
        return True  # No preference = matches everything
    return listing_methodology in buyer_preferences


def _score_price(listing_price: float, buyer_min: Optional[float], buyer_max: Optional[float]) -> bool:
    """Check if listing price is within buyer's range."""
    if buyer_min is None and buyer_max is None:
        return True
    if buyer_max is not None and listing_price > buyer_max:
        return False
    if buyer_min is not None and listing_price < buyer_min:
        return False
    return True


def _score_location(listing_location: Optional[str], buyer_locations: List[str]) -> bool:
    """Check if listing location matches buyer preference."""
    if not buyer_locations:
        return True
    if not listing_location:
        return False
    return listing_location in buyer_locations


def _score_timeline(listing_days: int, buyer_preference_days: int) -> bool:
    """Check if listing delivery timeline fits buyer's preference."""
    return listing_days <= buyer_preference_days * 1.5  # 50% tolerance


def _compute_match_score(
    listing: BrokerageListing,
    buyer: BuyerProfile,
) -> MatchResult:
    """
    Compute a composite match score (0.0 - 1.0).

    Weights:
        methodology: 30%
        price: 30%
        timeline: 20%
        location: 20%
    """
    methodology_match = _score_methodology(listing.methodology, buyer.preferred_methodologies)
    price_match = _score_price(
        listing.price_per_credit_usd,
        buyer.price_range_min_usd,
        buyer.price_range_max_usd,
    )
    location_match = _score_location(listing.location, buyer.preferred_locations)
    timeline_match = _score_timeline(listing.delivery_timeline_days, buyer.delivery_timeline_preference_days)

    score = 0.0
    if methodology_match:
        score += 0.30
    if price_match:
        score += 0.30
    if timeline_match:
        score += 0.20
    if location_match:
        score += 0.20

    return MatchResult(
        listing_id=listing.id,
        buyer_id=buyer.user_id,
        score=round(score, 3),
        methodology_match=methodology_match,
        price_match=price_match,
        location_match=location_match,
        timeline_match=timeline_match,
    )


class MatchingEngine:
    """High-level matching engine for brokerage listings."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_matches_for_listing(
        self,
        listing_id: uuid.UUID,
        limit: int = 10,
    ) -> List[MatchResult]:
        """Find the best buyer matches for a specific listing."""
        result = await self.db.execute(
            select(BrokerageListing).where(BrokerageListing.id == listing_id)
        )
        listing = result.scalar_one_or_none()
        if not listing:
            return []

        buyers_result = await self.db.execute(
            select(BuyerProfile).where(BuyerProfile.auto_match_enabled.is_(True))
        )
        buyers = buyers_result.scalars().all()

        matches = []
        for buyer in buyers:
            match = _compute_match_score(listing, buyer)
            if match.score >= MATCH_THRESHOLD:
                matches.append(match)

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:limit]

    async def find_matches_for_buyer(
        self,
        buyer_user_id: uuid.UUID,
        limit: int = 10,
    ) -> List[MatchResult]:
        """Find the best listings for a specific buyer."""
        result = await self.db.execute(
            select(BuyerProfile).where(BuyerProfile.user_id == buyer_user_id)
        )
        buyer = result.scalar_one_or_none()
        if not buyer:
            return []

        listings_result = await self.db.execute(
            select(BrokerageListing).where(BrokerageListing.status == "active")
        )
        listings = listings_result.scalars().all()

        matches = []
        for listing in listings:
            match = _compute_match_score(listing, buyer)
            if match.score >= MATCH_THRESHOLD:
                matches.append(match)

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:limit]

    async def save_match(self, match: MatchResult) -> TradeMatch:
        """Persist a match to the database."""
        trade_match = TradeMatch(
            listing_id=match.listing_id,
            buyer_id=match.buyer_id,
            match_score=match.score,
            methodology_match=match.methodology_match,
            price_match=match.price_match,
            location_match=match.location_match,
            timeline_match=match.timeline_match,
            status="suggested",
        )
        self.db.add(trade_match)
        await self.db.commit()
        await self.db.refresh(trade_match)
        logger.info("match_saved", match_id=str(trade_match.id), score=match.score)
        return trade_match

    async def run_global_matching(self) -> Dict[str, Any]:
        """Run matching for all active listings against all active buyers."""
        listings_result = await self.db.execute(
            select(BrokerageListing).where(BrokerageListing.status == "active")
        )
        listings = listings_result.scalars().all()

        buyers_result = await self.db.execute(
            select(BuyerProfile).where(BuyerProfile.auto_match_enabled.is_(True))
        )
        buyers = buyers_result.scalars().all()

        total_matches = 0
        for listing in listings:
            for buyer in buyers:
                match = _compute_match_score(listing, buyer)
                if match.score >= MATCH_THRESHOLD:
                    await self.save_match(match)
                    total_matches += 1

        logger.info("global_matching_complete", total_matches=total_matches)
        return {
            "listings_scanned": len(listings),
            "buyers_scanned": len(buyers),
            "matches_created": total_matches,
        }
