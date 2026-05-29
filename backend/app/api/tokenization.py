"""
Tokenization API for CarbonVerify.

Mint, fractionalize, list, buy, and retire carbon credit tokens on Radix DLT.
"""

import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import (
    User, Project, CarbonCreditToken, TokenListing, TokenRetirement,
)
from app.auth.dependencies import get_current_user, require_admin
from app.tokenization.token_service import TokenizationService
from app.schemas import (
    TokenMintRequest, CarbonCreditTokenOut, TokenListingCreate,
    TokenListingOut, TokenRetireRequest, TokenRetirementOut,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/tokenization", tags=["tokenization"])


async def _check_tokenization_enabled(project_id: uuid.UUID, db: AsyncSession):
    """Verify tokenization is enabled for a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.tokenization_enabled:
        raise HTTPException(status_code=403, detail="Tokenization not enabled for this project")
    return project


# ─── Token Minting ────────────────────────────────────────────────────────────

@router.post("/tokens/mint", response_model=CarbonCreditTokenOut, status_code=201)
async def mint_token(
    payload: TokenMintRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mint a new carbon credit token (admin only)."""
    await _check_tokenization_enabled(payload.project_id, db)

    service = TokenizationService(db)
    token = await service.mint_token(
        project_id=payload.project_id,
        calculation_run_id=payload.calculation_run_id,
        tonnes_co2e=payload.tonnes_co2e,
        vintage_year=payload.vintage_year,
        methodology=payload.methodology,
        vvb_registry=payload.vvb_registry,
        vvb_certificate_id=payload.vvb_certificate_id,
        metadata=payload.metadata,
    )
    return token


@router.post("/tokens/{token_id}/fractionalize")
async def fractionalize_token(
    token_id: uuid.UUID,
    fractions: List[float],
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Divide a token into fractional child tokens (admin only)."""
    service = TokenizationService(db)
    children = await service.fractionalize_token(token_id, fractions)
    return {
        "parent_id": str(token_id),
        "children": [
            {
                "id": str(c.id),
                "tonnes_co2e": c.tonnes_co2e,
                "radix_address": c.radix_token_address,
            }
            for c in children
        ],
    }


@router.get("/tokens", response_model=List[CarbonCreditTokenOut])
async def list_tokens(
    project_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List carbon credit tokens."""
    stmt = select(CarbonCreditToken).order_by(desc(CarbonCreditToken.created_at))
    if project_id:
        stmt = stmt.where(CarbonCreditToken.project_id == project_id)
    if status:
        stmt = stmt.where(CarbonCreditToken.status == status)
    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/tokens/{token_id}")
async def get_token(
    token_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a token with full provenance."""
    service = TokenizationService(db)
    token_data = await service.get_token_with_provenance(token_id)
    return token_data


# ─── Marketplace ──────────────────────────────────────────────────────────────

@router.post("/marketplace/list", response_model=TokenListingOut, status_code=201)
async def list_token_on_marketplace(
    payload: TokenListingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List a token for sale on the marketplace."""
    service = TokenizationService(db)
    listing = await service.list_token(
        token_id=payload.token_id,
        seller_id=current_user.id,
        price_per_tonne_usd=payload.price_per_tonne_usd,
        amount_available=payload.amount_available,
    )
    return listing


@router.get("/marketplace", response_model=List[TokenListingOut])
async def browse_marketplace(
    methodology: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Browse token marketplace listings."""
    stmt = select(TokenListing).where(TokenListing.status == "active").order_by(desc(TokenListing.created_at))
    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    listings = result.scalars().all()

    # Apply price filters in Python since we may need to join with token
    filtered = []
    for listing in listings:
        if min_price and listing.price_per_tonne_usd < min_price:
            continue
        if max_price and listing.price_per_tonne_usd > max_price:
            continue
        if methodology:
            # Would need to join with token for methodology filter
            pass
        filtered.append(listing)

    return filtered


@router.post("/marketplace/{listing_id}/buy")
async def buy_token(
    listing_id: uuid.UUID,
    tonnes_to_buy: float = Query(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Buy tokens from a marketplace listing."""
    service = TokenizationService(db)
    result = await service.buy_token(listing_id, current_user.id, tonnes_to_buy)
    return result


# ─── Retirement ───────────────────────────────────────────────────────────────

@router.post("/tokens/{token_id}/retire", response_model=TokenRetirementOut, status_code=201)
async def retire_token(
    token_id: uuid.UUID,
    payload: TokenRetireRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently retire a token for offset claims."""
    service = TokenizationService(db)
    retirement = await service.retire_token(
        token_id=token_id,
        retired_by=current_user.id,
        tonnes_retired=payload.tonnes_retired,
        purpose=payload.purpose,
        beneficiary_name=payload.beneficiary_name,
        beneficiary_location=payload.beneficiary_location,
    )
    return retirement


@router.get("/retirements")
async def list_retirements(
    token_id: Optional[uuid.UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List token retirements."""
    stmt = select(TokenRetirement).order_by(desc(TokenRetirement.created_at))
    if token_id:
        stmt = stmt.where(TokenRetirement.token_id == token_id)
    else:
        stmt = stmt.where(TokenRetirement.retired_by == current_user.id)
    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()
