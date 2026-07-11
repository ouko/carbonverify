"""
Corporate Buyer API for CarbonVerify.

Portfolio management, ESG reporting, and due diligence access.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, CorporatePortfolio, PortfolioHolding
from app.auth.dependencies import get_current_user
from app.brokerage.corporate_service import CorporateService
from app.schemas import ESGReportConfig, PortfolioHoldingOut
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/corporate", tags=["corporate"])


# ─── Portfolio ────────────────────────────────────────────────────────────────

@router.get("/portfolio")
async def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the corporate buyer's portfolio summary."""
    service = CorporateService(db)
    summary = await service.get_portfolio_summary(current_user.id)
    return summary


@router.get("/portfolio/holdings", response_model=List[PortfolioHoldingOut])
async def get_holdings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all holdings in the portfolio."""
    portfolio_result = await db.execute(
        select(CorporatePortfolio).where(CorporatePortfolio.user_id == current_user.id)
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if not portfolio:
        return []

    holdings_result = await db.execute(
        select(PortfolioHolding)
        .where(PortfolioHolding.portfolio_id == portfolio.id)
        .offset(skip)
        .limit(limit)
    )
    return holdings_result.scalars().all()


# ─── ESG Reporting ────────────────────────────────────────────────────────────

@router.post("/esg-report")
async def generate_esg_report(
    config: ESGReportConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate an auto-generated ESG offset report."""
    service = CorporateService(db)
    report = await service.generate_esg_report(
        user_id=current_user.id,
        company_name=config.company_name,
        reporting_period_start=config.reporting_period_start,
        reporting_period_end=config.reporting_period_end,
        scope=config.scope,
        sdgs=config.sdgs,
    )
    return report


@router.get("/esg-report/latest")
async def get_latest_esg_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recently generated ESG report."""
    portfolio_result = await db.execute(
        select(CorporatePortfolio).where(CorporatePortfolio.user_id == current_user.id)
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if not portfolio or not portfolio.esg_report_config:
        raise HTTPException(status_code=404, detail="No ESG report found")

    return portfolio.esg_report_config.get("last_report")


# ─── Due Diligence ────────────────────────────────────────────────────────────

@router.get("/due-diligence/{token_id}")
async def get_due_diligence_package(
    token_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the full due diligence package for a token.

    Includes MRV data, VVB certificates, project documentation,
    and calculation run details.
    """
    # Verify user holds this token
    portfolio_result = await db.execute(
        select(CorporatePortfolio).where(CorporatePortfolio.user_id == current_user.id)
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=403, detail="You do not hold this token")

    holding_result = await db.execute(
        select(PortfolioHolding).where(
            PortfolioHolding.portfolio_id == portfolio.id,
            PortfolioHolding.token_id == token_id,
        )
    )
    holding = holding_result.scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=403, detail="You do not hold this token")

    service = CorporateService(db)
    package = await service.get_due_diligence_package(token_id)
    return package
