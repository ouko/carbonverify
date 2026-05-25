"""
Corporate buyer service for CarbonVerify.

Manages buyer portfolios, generates ESG reports, and provides
due diligence access to underlying MRV data.
"""

import uuid
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    CorporatePortfolio, PortfolioHolding, CarbonCreditToken,
    TokenRetirement, Project, CalculationRun,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class CorporateService:
    """Service for corporate buyer portfolio management and ESG reporting."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_portfolio(self, user_id: uuid.UUID) -> CorporatePortfolio:
        """Get a user's portfolio, creating it if it doesn't exist."""
        result = await self.db.execute(
            select(CorporatePortfolio).where(CorporatePortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            portfolio = CorporatePortfolio(
                user_id=user_id,
                total_credits_held=0.0,
                total_credits_retired=0.0,
                portfolio_value_usd=0.0,
            )
            self.db.add(portfolio)
            await self.db.commit()
            await self.db.refresh(portfolio)
            logger.info("portfolio_created", user_id=str(user_id))

        return portfolio

    async def add_holding(
        self,
        user_id: uuid.UUID,
        token_id: uuid.UUID,
        tonnes: float,
        acquisition_price_usd: float,
    ) -> PortfolioHolding:
        """Add a token holding to a corporate portfolio."""
        portfolio = await self.get_or_create_portfolio(user_id)

        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            token_id=token_id,
            tonnes_held=tonnes,
            acquisition_price_usd=acquisition_price_usd,
        )
        self.db.add(holding)

        # Update portfolio totals
        portfolio.total_credits_held += tonnes
        portfolio.portfolio_value_usd += tonnes * acquisition_price_usd

        await self.db.commit()
        await self.db.refresh(holding)
        logger.info("holding_added", portfolio_id=str(portfolio.id), token_id=str(token_id), tonnes=tonnes)
        return holding

    async def get_portfolio_summary(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get a summary view of a corporate portfolio."""
        portfolio = await self.get_or_create_portfolio(user_id)

        # Get all holdings with token details
        holdings_result = await self.db.execute(
            select(PortfolioHolding, CarbonCreditToken, Project)
            .join(CarbonCreditToken, PortfolioHolding.token_id == CarbonCreditToken.id)
            .outerjoin(Project, CarbonCreditToken.project_id == Project.id)
            .where(PortfolioHolding.portfolio_id == portfolio.id)
        )
        holdings = holdings_result.all()

        # Calculate vintage distribution
        vintage_distribution: Dict[int, float] = {}
        methodology_breakdown: Dict[str, float] = {}
        project_contributions: List[Dict[str, Any]] = []

        for holding, token, project in holdings:
            # Vintage distribution
            vintage_distribution[token.vintage_year] = vintage_distribution.get(token.vintage_year, 0) + holding.tonnes_held

            # Methodology breakdown
            methodology_breakdown[token.methodology] = methodology_breakdown.get(token.methodology, 0) + holding.tonnes_held

            # Project contributions
            project_contributions.append({
                "project_id": str(project.id) if project else None,
                "project_name": project.name if project else None,
                "tonnes_held": holding.tonnes_held,
                "tonnes_retired": holding.tonnes_retired,
                "vintage": token.vintage_year,
                "methodology": token.methodology,
                "vvb_registry": token.vvb_registry,
            })

        # Get retirement history
        retirements_result = await self.db.execute(
            select(TokenRetirement, CarbonCreditToken)
            .join(CarbonCreditToken, TokenRetirement.token_id == CarbonCreditToken.id)
            .where(TokenRetirement.retired_by == user_id)
        )
        retirements = retirements_result.all()

        total_retired = sum(r.tonnes_retired for r, _ in retirements)

        return {
            "portfolio_id": str(portfolio.id),
            "total_credits_held": portfolio.total_credits_held,
            "total_credits_retired": total_retired,
            "portfolio_value_usd": portfolio.portfolio_value_usd,
            "vintage_distribution": vintage_distribution,
            "methodology_breakdown": methodology_breakdown,
            "project_contributions": project_contributions,
            "holdings_count": len(holdings),
            "retirements_count": len(retirements),
        }

    async def generate_esg_report(
        self,
        user_id: uuid.UUID,
        company_name: str,
        reporting_period_start: date,
        reporting_period_end: date,
        scope: str = "Scope 3",
        sdgs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate an auto-generated ESG offset report.

        Includes:
        - Total offsets acquired and retired
        - Vintage distribution
        - Methodology breakdown
        - SDG impact summaries
        - Project-level contributions
        """
        portfolio = await self.get_or_create_portfolio(user_id)

        # Get holdings within reporting period
        holdings_result = await self.db.execute(
            select(PortfolioHolding, CarbonCreditToken, Project)
            .join(CarbonCreditToken, PortfolioHolding.token_id == CarbonCreditToken.id)
            .outerjoin(Project, CarbonCreditToken.project_id == Project.id)
            .where(
                PortfolioHolding.portfolio_id == portfolio.id,
                PortfolioHolding.acquired_at >= datetime.combine(reporting_period_start, datetime.min.time()),
                PortfolioHolding.acquired_at <= datetime.combine(reporting_period_end, datetime.max.time()),
            )
        )
        holdings = holdings_result.all()

        # Get retirements within period
        retirements_result = await self.db.execute(
            select(TokenRetirement, CarbonCreditToken)
            .join(CarbonCreditToken, TokenRetirement.token_id == CarbonCreditToken.id)
            .where(
                TokenRetirement.retired_by == user_id,
                TokenRetirement.created_at >= datetime.combine(reporting_period_start, datetime.min.time()),
                TokenRetirement.created_at <= datetime.combine(reporting_period_end, datetime.max.time()),
            )
        )
        retirements = retirements_result.all()

        total_offsets = sum(h.tonnes_held for h, _, _ in holdings)
        total_retired = sum(r.tonnes_retired for r, _ in retirements)

        # Vintage distribution
        vintage_distribution: Dict[int, float] = {}
        methodology_breakdown: Dict[str, float] = {}
        project_contributions: List[Dict[str, Any]] = []

        for holding, token, project in holdings:
            vintage_distribution[token.vintage_year] = vintage_distribution.get(token.vintage_year, 0) + holding.tonnes_held
            methodology_breakdown[token.methodology] = methodology_breakdown.get(token.methodology, 0) + holding.tonnes_held

            project_contributions.append({
                "project_name": project.name if project else None,
                "project_location": project.developer.company_name if project and hasattr(project, 'developer') and project.developer else None,
                "tonnes_acquired": holding.tonnes_held,
                "tonnes_retired": holding.tonnes_retired,
                "vintage": token.vintage_year,
                "methodology": token.methodology,
                "vvb_registry": token.vvb_registry,
                "co_benefits": project.metadata_json.get("co_benefits", []) if project and hasattr(project, 'metadata_json') else [],
            })

        # SDG impact mapping (simplified)
        sdg_impact = {
            "SDG 7": "Affordable and Clean Energy — cookstove projects reduce fuelwood consumption",
            "SDG 13": "Climate Action — verified emissions reductions",
            "SDG 3": "Good Health — reduced indoor air pollution from clean cooking",
            "SDG 15": "Life on Land — forest conservation through reduced charcoal demand",
        }
        selected_sdgs = {k: v for k, v in sdg_impact.items() if not sdgs or k in sdgs}

        report = {
            "company_name": company_name,
            "reporting_period": f"{reporting_period_start.isoformat()} to {reporting_period_end.isoformat()}",
            "scope": scope,
            "total_offsets_tco2e": round(total_offsets, 2),
            "total_retired_tco2e": round(total_retired, 2),
            "net_offsets_held_tco2e": round(total_offsets - total_retired, 2),
            "vintage_distribution": vintage_distribution,
            "methodology_breakdown": methodology_breakdown,
            "sdg_impact_summary": selected_sdgs,
            "project_contributions": project_contributions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_id": str(uuid.uuid4()),
        }

        # Save report config
        portfolio.esg_report_config = {
            "last_report": report,
            "company_name": company_name,
            "scope": scope,
            "sdgs": sdgs or [],
        }
        await self.db.commit()

        logger.info(
            "esg_report_generated",
            user_id=str(user_id),
            company_name=company_name,
            total_offsets=total_offsets,
        )
        return report

    async def get_due_diligence_package(self, token_id: uuid.UUID) -> Dict[str, Any]:
        """
        Retrieve the full due diligence package for a token.

        Includes MRV data, VVB certificates, project documentation,
        and calculation run details.
        """
        token_result = await self.db.execute(
            select(CarbonCreditToken).where(CarbonCreditToken.id == token_id)
        )
        token = token_result.scalar_one_or_none()
        if not token:
            raise ValueError("Token not found")

        calc_result = await self.db.execute(
            select(CalculationRun).where(CalculationRun.id == token.calculation_run_id)
        )
        calc = calc_result.scalar_one_or_none()

        proj_result = await self.db.execute(
            select(Project).where(Project.id == token.project_id)
        )
        project = proj_result.scalar_one_or_none()

        retirement_result = await self.db.execute(
            select(TokenRetirement).where(TokenRetirement.token_id == token_id)
        )
        retirements = retirement_result.scalars().all()

        return {
            "token_id": str(token.id),
            "vintage": token.vintage_year,
            "methodology": token.methodology,
            "vvb_registry": token.vvb_registry,
            "vvb_certificate_id": token.vvb_certificate_id,
            "radix_token_address": token.radix_token_address,
            "project": {
                "id": str(project.id) if project else None,
                "name": project.name if project else None,
                "crediting_period_start": project.crediting_period_start if project else None,
                "crediting_period_end": project.crediting_period_end if project else None,
            },
            "calculation_run": {
                "id": str(calc.id) if calc else None,
                "fnrb_value": calc.fNRB_value if calc else None,
                "emissions_reduction_tCO2e": calc.emissions_reduction_tCO2e if calc else None,
                "uncertainty_95CI": calc.uncertainty_95CI if calc else None,
                "methodology_compliance_score": calc.methodology_compliance_score if calc else None,
                "confidence_score": calc.confidence_score if calc else None,
            },
            "mrv_provenance": token.metadata_json.get("mrv_data", {}),
            "retirement_status": {
                "is_retired": token.status.value == "retired",
                "retirements": [
                    {
                        "tonnes": r.tonnes_retired,
                        "purpose": r.purpose,
                        "beneficiary": r.beneficiary_name,
                        "date": r.created_at.isoformat(),
                        "burn_tx": r.radix_burn_tx_ref,
                    }
                    for r in retirements
                ],
            },
        }
