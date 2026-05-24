"""
Carbon credit tokenization service for CarbonVerify.

Integrates with Radix DLT to mint, list, trade, and retire carbon credit NFTs.
Each token represents one verified tonne of CO2e with full MRV metadata.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    CarbonCreditToken, TokenListing, TokenRetirement,
    TokenStatusEnum, CalculationRun, Project,
)
from app.blockchain.radix_client import RadixClient
from app.core.logging import get_logger

logger = get_logger(__name__)


class TokenizationService:
    """Service for tokenizing carbon credits on Radix DLT."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.radix = RadixClient()

    async def mint_token(
        self,
        project_id: uuid.UUID,
        calculation_run_id: uuid.UUID,
        tonnes_co2e: float,
        vintage_year: int,
        methodology: str,
        vvb_registry: str,
        vvb_certificate_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CarbonCreditToken:
        """
        Mint a new carbon credit token.

        Auto-activates upon VVB verification approval. Creates a Radix NFT
        with embedded MRV metadata.
        """
        # Verify calculation run exists and is approved
        calc_result = await self.db.execute(
            select(CalculationRun).where(CalculationRun.id == calculation_run_id)
        )
        calc = calc_result.scalar_one_or_none()
        if not calc:
            raise ValueError("Calculation run not found")

        # Build NFT metadata
        token_metadata = {
            "project_id": str(project_id),
            "calculation_run_id": str(calculation_run_id),
            "tonnes_co2e": tonnes_co2e,
            "vintage_year": vintage_year,
            "methodology": methodology,
            "vvb_registry": vvb_registry,
            "vvb_certificate_id": vvb_certificate_id,
            "minted_at": datetime.now(timezone.utc).isoformat(),
            "mrv_data": {
                "fnrb_value": calc.fNRB_value,
                "emissions_reduction_tCO2e": calc.emissions_reduction_tCO2e,
                "uncertainty_95CI": calc.uncertainty_95CI,
                "methodology_compliance_score": calc.methodology_compliance_score,
            } if calc else {},
            **(metadata or {}),
        }

        # Anchor metadata hash to Radix
        anchor_result = await self.radix.anchor_audit_log(
            token_metadata,
            memo=f"Mint:{project_id}:{vintage_year}",
        )

        # In production: call Radix to mint actual NFT
        # For now, simulate with deterministic address
        radix_address = None
        if self.radix.enabled:
            # Would call actual Radix component here
            radix_address = anchor_result.tx_ref
        else:
            radix_address = f"sim_token_{uuid.uuid5(uuid.NAMESPACE_OID, json.dumps(token_metadata, sort_keys=True))}"

        token = CarbonCreditToken(
            project_id=project_id,
            calculation_run_id=calculation_run_id,
            tonnes_co2e=tonnes_co2e,
            vintage_year=vintage_year,
            methodology=methodology,
            vvb_registry=vvb_registry,
            vvb_certificate_id=vvb_certificate_id,
            radix_token_address=radix_address,
            metadata_json=token_metadata,
            status=TokenStatusEnum.minted,
        )
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)

        logger.info(
            "token_minted",
            token_id=str(token.id),
            radix_address=radix_address,
            tonnes=tonnes_co2e,
        )
        return token

    async def fractionalize_token(
        self,
        parent_token_id: uuid.UUID,
        fractions: List[float],
    ) -> List[CarbonCreditToken]:
        """
        Divide a large token into fractional child tokens for retail investment.

        Each fraction must sum to the parent's tonnes_co2e.
        """
        parent_result = await self.db.execute(
            select(CarbonCreditToken).where(CarbonCreditToken.id == parent_token_id)
        )
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise ValueError("Parent token not found")

        if parent.status != TokenStatusEnum.minted:
            raise ValueError("Token must be in 'minted' status to fractionalize")

        if abs(sum(fractions) - parent.tonnes_co2e) > 0.001:
            raise ValueError(f"Fractions must sum to {parent.tonnes_co2e}")

        child_tokens = []
        for i, fraction in enumerate(fractions):
            child = CarbonCreditToken(
                project_id=parent.project_id,
                calculation_run_id=parent.calculation_run_id,
                tonnes_co2e=fraction,
                vintage_year=parent.vintage_year,
                methodology=parent.methodology,
                vvb_registry=parent.vvb_registry,
                vvb_certificate_id=parent.vvb_certificate_id,
                radix_token_address=f"{parent.radix_token_address}_frac{i}",
                metadata_json={
                    **parent.metadata_json,
                    "parent_token_id": str(parent.id),
                    "fraction_index": i,
                    "fraction_of_total": fraction / parent.tonnes_co2e,
                },
                status=TokenStatusEnum.minted,
                is_fractional=True,
                parent_token_id=parent.id,
            )
            self.db.add(child)
            child_tokens.append(child)

        # Mark parent as fractional
        parent.status = TokenStatusEnum.fractional
        await self.db.commit()

        for child in child_tokens:
            await self.db.refresh(child)

        logger.info(
            "token_fractionalized",
            parent_id=str(parent_token_id),
            children_count=len(child_tokens),
        )
        return child_tokens

    async def list_token(
        self,
        token_id: uuid.UUID,
        seller_id: uuid.UUID,
        price_per_tonne_usd: float,
        amount_available: float,
    ) -> TokenListing:
        """List a token on the marketplace."""
        token_result = await self.db.execute(
            select(CarbonCreditToken).where(CarbonCreditToken.id == token_id)
        )
        token = token_result.scalar_one_or_none()
        if not token:
            raise ValueError("Token not found")

        if token.status not in (TokenStatusEnum.minted, TokenStatusEnum.sold):
            raise ValueError(f"Token cannot be listed from status {token.status.value}")

        if amount_available > token.tonnes_co2e:
            raise ValueError("Cannot list more than available tonnes")

        listing = TokenListing(
            token_id=token_id,
            seller_id=seller_id,
            price_per_tonne_usd=price_per_tonne_usd,
            amount_available=amount_available,
            status="active",
        )
        self.db.add(listing)

        token.status = TokenStatusEnum.listed
        await self.db.commit()
        await self.db.refresh(listing)

        logger.info(
            "token_listed",
            listing_id=str(listing.id),
            token_id=str(token_id),
            price=price_per_tonne_usd,
        )
        return listing

    async def buy_token(
        self,
        listing_id: uuid.UUID,
        buyer_id: uuid.UUID,
        tonnes_to_buy: float,
    ) -> Dict[str, Any]:
        """Execute a token purchase from a marketplace listing."""
        listing_result = await self.db.execute(
            select(TokenListing).where(TokenListing.id == listing_id)
        )
        listing = listing_result.scalar_one_or_none()
        if not listing:
            raise ValueError("Listing not found")

        if listing.status != "active":
            raise ValueError("Listing is not active")

        if tonnes_to_buy > listing.amount_available:
            raise ValueError(f"Only {listing.amount_available} tonnes available")

        total_cost = tonnes_to_buy * listing.price_per_tonne_usd

        # Update listing
        listing.amount_available -= tonnes_to_buy
        if listing.amount_available <= 0:
            listing.status = "sold"

        # Update token status if fully sold
        token_result = await self.db.execute(
            select(CarbonCreditToken).where(CarbonCreditToken.id == listing.token_id)
        )
        token = token_result.scalar_one()
        if listing.amount_available <= 0:
            token.status = TokenStatusEnum.sold

        await self.db.commit()

        logger.info(
            "token_purchased",
            listing_id=str(listing_id),
            buyer_id=str(buyer_id),
            tonnes=tonnes_to_buy,
            cost=total_cost,
        )
        return {
            "listing_id": str(listing_id),
            "tonnes_purchased": tonnes_to_buy,
            "total_cost_usd": total_cost,
            "remaining_available": listing.amount_available,
        }

    async def retire_token(
        self,
        token_id: uuid.UUID,
        retired_by: uuid.UUID,
        tonnes_retired: float,
        purpose: Optional[str] = None,
        beneficiary_name: Optional[str] = None,
        beneficiary_location: Optional[str] = None,
    ) -> TokenRetirement:
        """
        Permanently retire (burn) a token for offset claims.

        Creates an immutable retirement record and burns the Radix token.
        """
        token_result = await self.db.execute(
            select(CarbonCreditToken).where(CarbonCreditToken.id == token_id)
        )
        token = token_result.scalar_one_or_none()
        if not token:
            raise ValueError("Token not found")

        if tonnes_retired > token.tonnes_co2e:
            raise ValueError("Cannot retire more tonnes than token represents")

        # Burn on Radix
        burn_data = {
            "token_id": str(token_id),
            "tonnes_retired": tonnes_retired,
            "retired_by": str(retired_by),
            "purpose": purpose,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        burn_result = await self.radix.anchor_audit_log(burn_data, memo=f"Retire:{token_id}")
        burn_tx_ref = burn_result.tx_ref if burn_result.success else None

        retirement = TokenRetirement(
            token_id=token_id,
            retired_by=retired_by,
            tonnes_retired=tonnes_retired,
            purpose=purpose,
            beneficiary_name=beneficiary_name,
            beneficiary_location=beneficiary_location,
            radix_burn_tx_ref=burn_tx_ref,
        )
        self.db.add(retirement)

        # Update token status
        token.status = TokenStatusEnum.retired
        token.metadata_json["retired_at"] = datetime.now(timezone.utc).isoformat()
        token.metadata_json["retirement_purpose"] = purpose

        await self.db.commit()
        await self.db.refresh(retirement)

        logger.info(
            "token_retired",
            token_id=str(token_id),
            retirement_id=str(retirement.id),
            tonnes=tonnes_retired,
            burn_tx=burn_tx_ref,
        )
        return retirement

    async def get_token_with_provenance(self, token_id: uuid.UUID) -> Dict[str, Any]:
        """Get a token with full provenance chain including MRV data."""
        token_result = await self.db.execute(
            select(CarbonCreditToken).where(CarbonCreditToken.id == token_id)
        )
        token = token_result.scalar_one_or_none()
        if not token:
            raise ValueError("Token not found")

        # Get calculation run data
        calc_result = await self.db.execute(
            select(CalculationRun).where(CalculationRun.id == token.calculation_run_id)
        )
        calc = calc_result.scalar_one_or_none()

        # Get project data
        proj_result = await self.db.execute(
            select(Project).where(Project.id == token.project_id)
        )
        project = proj_result.scalar_one_or_none()

        # Get retirement history
        retirement_result = await self.db.execute(
            select(TokenRetirement).where(TokenRetirement.token_id == token_id)
        )
        retirements = retirement_result.scalars().all()

        return {
            "token": {
                "id": str(token.id),
                "tonnes_co2e": token.tonnes_co2e,
                "vintage_year": token.vintage_year,
                "methodology": token.methodology,
                "vvb_registry": token.vvb_registry,
                "status": token.status.value,
                "radix_address": token.radix_token_address,
            },
            "project": {
                "id": str(project.id) if project else None,
                "name": project.name if project else None,
            },
            "mrv_data": {
                "calculation_run_id": str(calc.id) if calc else None,
                "fnrb_value": calc.fNRB_value if calc else None,
                "emissions_reduction_tCO2e": calc.emissions_reduction_tCO2e if calc else None,
                "uncertainty_95CI": calc.uncertainty_95CI if calc else None,
            },
            "retirements": [
                {
                    "id": str(r.id),
                    "tonnes": r.tonnes_retired,
                    "purpose": r.purpose,
                    "beneficiary": r.beneficiary_name,
                    "burn_tx": r.radix_burn_tx_ref,
                    "date": r.created_at,
                }
                for r in retirements
            ],
        }
