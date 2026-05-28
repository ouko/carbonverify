"""
Brokerage API for CarbonVerify.

Buyer-seller matching, transaction execution, escrow management,
and commission tracking.
"""

import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import (
    User, Project, BrokerageListing, BuyerProfile, Commission, ListingStatusEnum,
    TradeTypeEnum,
)
from app.auth.dependencies import get_current_user, require_operator
from app.brokerage.matching_engine import MatchingEngine
from app.brokerage.transaction_engine import TransactionEngine
from app.schemas import (
    BrokerageListingCreate, BrokerageListingOut, BuyerProfileCreate,
    BuyerProfileOut, TransactionCreate, TransactionOut,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/brokerage", tags=["brokerage"])


async def _check_brokerage_enabled(project_id: uuid.UUID, db: AsyncSession):
    """Verify brokerage is enabled for a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.brokerage_enabled:
        raise HTTPException(status_code=403, detail="Brokerage not enabled for this project")
    return project


# ─── Listings ─────────────────────────────────────────────────────────────────

@router.post("/listings", response_model=BrokerageListingOut, status_code=201)
async def create_listing(
    payload: BrokerageListingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new credit listing (seller)."""
    await _check_brokerage_enabled(payload.project_id, db)

    listing = BrokerageListing(
        project_id=payload.project_id,
        seller_id=current_user.id,
        available_credits=payload.available_credits,
        price_per_credit_usd=payload.price_per_credit_usd,
        vintage_year=payload.vintage_year,
        methodology=payload.methodology,
        co_benefits=payload.co_benefits,
        delivery_timeline_days=payload.delivery_timeline_days,
        location=payload.location,
        minimum_purchase=payload.minimum_purchase,
        metadata_json=payload.metadata,
        status=ListingStatusEnum.active,
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing


@router.get("/listings", response_model=List[BrokerageListingOut])
async def list_listings(
    project_id: Optional[uuid.UUID] = None,
    methodology: Optional[str] = None,
    status: Optional[str] = "active",
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Browse available credit listings."""
    stmt = select(BrokerageListing).order_by(desc(BrokerageListing.created_at))
    if project_id:
        stmt = stmt.where(BrokerageListing.project_id == project_id)
    if methodology:
        stmt = stmt.where(BrokerageListing.methodology == methodology)
    if status:
        stmt = stmt.where(BrokerageListing.status == status)
    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/listings/{listing_id}", response_model=BrokerageListingOut)
async def get_listing(listing_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single listing."""
    result = await db.execute(select(BrokerageListing).where(BrokerageListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


# ─── Buyer Profiles ───────────────────────────────────────────────────────────

@router.post("/buyers", response_model=BuyerProfileOut, status_code=201)
async def create_buyer_profile(
    payload: BuyerProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a buyer profile."""
    result = await db.execute(select(BuyerProfile).where(BuyerProfile.user_id == current_user.id))
    existing = result.scalar_one_or_none()

    if existing:
        for field, value in payload.model_dump().items():
            setattr(existing, field, value)
        await db.commit()
        await db.refresh(existing)
        return existing

    profile = BuyerProfile(user_id=current_user.id, **payload.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/buyers/me", response_model=BuyerProfileOut)
async def get_my_buyer_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's buyer profile."""
    result = await db.execute(select(BuyerProfile).where(BuyerProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Buyer profile not found")
    return profile


# ─── Matching ─────────────────────────────────────────────────────────────────

@router.post("/match/listing/{listing_id}")
async def find_matches_for_listing(
    listing_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find buyer matches for a listing."""
    engine = MatchingEngine(db)
    matches = await engine.find_matches_for_listing(listing_id, limit=limit)
    return {
        "listing_id": str(listing_id),
        "matches": [
            {
                "buyer_id": str(m.buyer_id),
                "score": m.score,
                "methodology_match": m.methodology_match,
                "price_match": m.price_match,
                "location_match": m.location_match,
                "timeline_match": m.timeline_match,
            }
            for m in matches
        ],
    }


@router.post("/match/buyer")
async def find_matches_for_buyer(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find listings matching the current buyer's profile."""
    engine = MatchingEngine(db)
    matches = await engine.find_matches_for_buyer(current_user.id, limit=limit)
    return {
        "buyer_id": str(current_user.id),
        "matches": [
            {
                "listing_id": str(m.listing_id),
                "score": m.score,
                "methodology_match": m.methodology_match,
                "price_match": m.price_match,
                "location_match": m.location_match,
                "timeline_match": m.timeline_match,
            }
            for m in matches
        ],
    }


@router.post("/match/run-global")
async def run_global_matching(
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Run global matching for all listings and buyers (admin/operator)."""
    engine = MatchingEngine(db)
    result = await engine.run_global_matching()
    return result


# ─── Transactions ─────────────────────────────────────────────────────────────

@router.get("/transactions", response_model=List[TransactionOut])
async def list_transactions(
    buyer_id: Optional[uuid.UUID] = None,
    seller_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List transactions (buyer or seller view)."""
    from sqlalchemy import select, desc
    from app.models import BrokerageTransaction
    stmt = select(BrokerageTransaction).order_by(desc(BrokerageTransaction.created_at))
    if buyer_id:
        stmt = stmt.where(BrokerageTransaction.buyer_id == buyer_id)
    if seller_id:
        stmt = stmt.where(BrokerageTransaction.seller_id == seller_id)
    if status:
        stmt = stmt.where(BrokerageTransaction.status == status)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/transactions", response_model=TransactionOut, status_code=201)
async def create_transaction(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new transaction from a listing."""
    engine = TransactionEngine(db)
    tx = await engine.create_transaction(
        listing_id=payload.listing_id,
        buyer_id=current_user.id,
        credits_amount=payload.credits_amount,
        trade_type=TradeTypeEnum(payload.trade_type),
        delivery_date=payload.delivery_date,
    )
    return tx


@router.post("/transactions/{transaction_id}/confirm")
async def confirm_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm a pending transaction."""
    engine = TransactionEngine(db)
    tx = await engine.confirm_transaction(transaction_id)
    return tx


@router.post("/transactions/{transaction_id}/execute-spot")
async def execute_spot(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute a spot trade."""
    engine = TransactionEngine(db)
    tx = await engine.execute_spot_trade(transaction_id)
    return tx


@router.get("/transactions/{transaction_id}/summary")
async def get_transaction_summary(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full transaction summary including escrow and commission."""
    engine = TransactionEngine(db)
    summary = await engine.get_transaction_summary(transaction_id)
    return summary


from pydantic import BaseModel

class CancelTransactionRequest(BaseModel):
    reason: str


@router.post("/transactions/{transaction_id}/cancel")
async def cancel_transaction(
    transaction_id: uuid.UUID,
    payload: CancelTransactionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a transaction (buyer or seller)."""
    engine = TransactionEngine(db)
    tx = await engine.cancel_transaction(transaction_id, payload.reason)
    return tx


# ─── Escrow ───────────────────────────────────────────────────────────────────

@router.post("/escrow/{transaction_id}/deposit")
async def deposit_escrow(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Buyer deposits payment into escrow."""
    engine = TransactionEngine(db)
    escrow = await engine.deposit_escrow(transaction_id)
    return escrow


@router.post("/escrow/{transaction_id}/confirm-transfer")
async def confirm_credit_transfer(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Seller confirms credit transfer to buyer."""
    engine = TransactionEngine(db)
    escrow = await engine.confirm_credit_transfer(transaction_id)
    return escrow


@router.post("/escrow/{transaction_id}/release")
async def release_escrow(
    transaction_id: uuid.UUID,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Operator manually releases escrow."""
    engine = TransactionEngine(db)
    tx = await engine.release_escrow(transaction_id)
    return tx


# ─── Commissions ──────────────────────────────────────────────────────────────

@router.get("/commissions")
async def list_commissions(
    invoiced: Optional[bool] = None,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """List commission records (operator/admin)."""
    stmt = select(Commission).order_by(desc(Commission.created_at))
    if invoiced is not None:
        stmt = stmt.where(Commission.invoiced == invoiced)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/commissions/{commission_id}/invoice")
async def invoice_commission(
    commission_id: uuid.UUID,
    invoice_number: str,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    """Generate an invoice for a commission."""
    engine = TransactionEngine(db)
    commission = await engine.generate_invoice(commission_id, invoice_number)
    return commission
