"""
Transaction execution engine for CarbonVerify brokerage.

Supports:
- Spot trades: immediate transfer
- Forward contracts: future delivery, fixed price
- Escrow: payment held until credit transfer confirmed

Commission: 2.5% default, auto-calculated and tracked.
"""

import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    BrokerageListing, BrokerageTransaction, Escrow, Commission,
    TransactionStatusEnum, TradeTypeEnum, ListingStatusEnum,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_COMMISSION_RATE = 0.025  # 2.5%


class TransactionEngine:
    """Executes and manages brokerage transactions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transaction(
        self,
        listing_id: uuid.UUID,
        buyer_id: uuid.UUID,
        credits_amount: float,
        trade_type: TradeTypeEnum,
        delivery_date: Optional[date] = None,
        commission_rate: float = DEFAULT_COMMISSION_RATE,
    ) -> BrokerageTransaction:
        """
        Create a new transaction from a listing.

        Validates:
        - Listing has sufficient credits
        - Credits >= listing.minimum_purchase
        """
        result = await self.db.execute(
            select(BrokerageListing).where(BrokerageListing.id == listing_id)
        )
        listing = result.scalar_one_or_none()
        if not listing:
            raise ValueError("Listing not found")

        if listing.status != ListingStatusEnum.active:
            raise ValueError("Listing is not active")

        if credits_amount > listing.available_credits:
            raise ValueError(f"Insufficient credits. Available: {listing.available_credits}")

        if credits_amount < listing.minimum_purchase:
            raise ValueError(f"Minimum purchase is {listing.minimum_purchase} credits")

        total_value = credits_amount * listing.price_per_credit_usd
        commission_usd = total_value * commission_rate

        # Determine delivery date for forwards
        if trade_type == TradeTypeEnum.forward and not delivery_date:
            delivery_date = date.today() + timedelta(days=listing.delivery_timeline_days)

        transaction = BrokerageTransaction(
            listing_id=listing_id,
            buyer_id=buyer_id,
            seller_id=listing.seller_id,
            trade_type=trade_type,
            credits_amount=credits_amount,
            price_per_credit_usd=listing.price_per_credit_usd,
            total_value_usd=total_value,
            commission_rate=commission_rate,
            commission_usd=commission_usd,
            status=TransactionStatusEnum.pending,
            delivery_date=delivery_date,
        )
        self.db.add(transaction)
        await self.db.flush()

        # For escrow trades, create escrow record
        if trade_type == TradeTypeEnum.escrow:
            escrow = Escrow(
                transaction_id=transaction.id,
                amount_usd=total_value,
                status="holding",
            )
            self.db.add(escrow)

        # Create commission record
        commission = Commission(
            transaction_id=transaction.id,
            amount_usd=commission_usd,
            rate=commission_rate,
        )
        self.db.add(commission)

        # Reserve credits from listing
        listing.available_credits -= credits_amount
        if listing.available_credits <= 0:
            listing.status = ListingStatusEnum.sold

        await self.db.commit()
        await self.db.refresh(transaction)

        logger.info(
            "transaction_created",
            transaction_id=str(transaction.id),
            trade_type=trade_type.value,
            total_value=total_value,
            commission=commission_usd,
        )
        return transaction

    async def confirm_transaction(self, transaction_id: uuid.UUID) -> BrokerageTransaction:
        """Confirm a pending transaction (buyer commitment)."""
        result = await self.db.execute(
            select(BrokerageTransaction).where(BrokerageTransaction.id == transaction_id)
        )
        tx = result.scalar_one_or_none()
        if not tx:
            raise ValueError("Transaction not found")

        if tx.status != TransactionStatusEnum.pending:
            raise ValueError(f"Transaction cannot be confirmed from status {tx.status.value}")

        tx.status = TransactionStatusEnum.confirmed
        await self.db.commit()
        logger.info("transaction_confirmed", transaction_id=str(transaction_id))
        return tx

    async def execute_spot_trade(self, transaction_id: uuid.UUID) -> BrokerageTransaction:
        """
        Execute a spot trade immediately.

        Both parties must have confirmed. Credits and payment transfer simultaneously.
        """
        result = await self.db.execute(
            select(BrokerageTransaction).where(BrokerageTransaction.id == transaction_id)
        )
        tx = result.scalar_one_or_none()
        if not tx:
            raise ValueError("Transaction not found")

        if tx.trade_type != TradeTypeEnum.spot:
            raise ValueError("Not a spot trade")

        if tx.status != TransactionStatusEnum.confirmed:
            raise ValueError("Transaction not confirmed")

        tx.status = TransactionStatusEnum.completed
        await self.db.commit()

        logger.info("spot_trade_executed", transaction_id=str(transaction_id))
        return tx

    async def deposit_escrow(self, transaction_id: uuid.UUID) -> Escrow:
        """Buyer deposits payment into escrow."""
        result = await self.db.execute(
            select(Escrow).where(Escrow.transaction_id == transaction_id)
        )
        escrow = result.scalar_one_or_none()
        if not escrow:
            raise ValueError("Escrow not found")

        escrow.buyer_deposited = True
        await self.db.commit()
        logger.info("escrow_deposited", transaction_id=str(transaction_id))
        return escrow

    async def confirm_credit_transfer(self, transaction_id: uuid.UUID) -> Escrow:
        """Seller confirms credit transfer to buyer."""
        result = await self.db.execute(
            select(Escrow).where(Escrow.transaction_id == transaction_id)
        )
        escrow = result.scalar_one_or_none()
        if not escrow:
            raise ValueError("Escrow not found")

        escrow.seller_transferred = True

        # Auto-release if both conditions met
        if escrow.buyer_deposited and escrow.seller_transferred:
            escrow.status = "released"
            escrow.released_at = datetime.now(timezone.utc)

            # Complete the transaction
            tx_result = await self.db.execute(
                select(BrokerageTransaction).where(BrokerageTransaction.id == transaction_id)
            )
            tx = tx_result.scalar_one()
            tx.status = TransactionStatusEnum.completed

        await self.db.commit()
        logger.info("credit_transfer_confirmed", transaction_id=str(transaction_id))
        return escrow

    async def release_escrow(self, transaction_id: uuid.UUID) -> BrokerageTransaction:
        """Manually release escrow (admin/operator override)."""
        result = await self.db.execute(
            select(Escrow).where(Escrow.transaction_id == transaction_id)
        )
        escrow = result.scalar_one_or_none()
        if not escrow:
            raise ValueError("Escrow not found")

        escrow.status = "released"
        escrow.released_at = datetime.now(timezone.utc)

        tx_result = await self.db.execute(
            select(BrokerageTransaction).where(BrokerageTransaction.id == transaction_id)
        )
        tx = tx_result.scalar_one()
        tx.status = TransactionStatusEnum.completed

        await self.db.commit()
        logger.info("escrow_released", transaction_id=str(transaction_id))
        return tx

    async def cancel_transaction(self, transaction_id: uuid.UUID, reason: str) -> BrokerageTransaction:
        """Cancel a transaction and restore credits to listing."""
        result = await self.db.execute(
            select(BrokerageTransaction).where(BrokerageTransaction.id == transaction_id)
        )
        tx = result.scalar_one_or_none()
        if not tx:
            raise ValueError("Transaction not found")

        if tx.status == TransactionStatusEnum.completed:
            raise ValueError("Cannot cancel a completed transaction")

        # Restore credits to listing
        listing_result = await self.db.execute(
            select(BrokerageListing).where(BrokerageListing.id == tx.listing_id)
        )
        listing = listing_result.scalar_one()
        listing.available_credits += tx.credits_amount
        if listing.status == ListingStatusEnum.sold:
            listing.status = ListingStatusEnum.active

        tx.status = TransactionStatusEnum.cancelled
        tx.metadata_json["cancellation_reason"] = reason

        await self.db.commit()
        logger.info("transaction_cancelled", transaction_id=str(transaction_id), reason=reason)
        return tx

    async def generate_invoice(self, commission_id: uuid.UUID, invoice_number: str) -> Commission:
        """Generate an invoice for a commission."""
        result = await self.db.execute(
            select(Commission).where(Commission.id == commission_id)
        )
        commission = result.scalar_one_or_none()
        if not commission:
            raise ValueError("Commission not found")

        commission.invoiced = True
        commission.invoice_number = invoice_number
        await self.db.commit()
        logger.info("commission_invoiced", commission_id=str(commission_id), invoice_number=invoice_number)
        return commission

    async def get_transaction_summary(self, transaction_id: uuid.UUID) -> Dict[str, Any]:
        """Get a complete summary of a transaction including escrow and commission."""
        tx_result = await self.db.execute(
            select(BrokerageTransaction).where(BrokerageTransaction.id == transaction_id)
        )
        tx = tx_result.scalar_one_or_none()
        if not tx:
            raise ValueError("Transaction not found")

        escrow_result = await self.db.execute(
            select(Escrow).where(Escrow.transaction_id == transaction_id)
        )
        escrow = escrow_result.scalar_one_or_none()

        commission_result = await self.db.execute(
            select(Commission).where(Commission.transaction_id == transaction_id)
        )
        commission = commission_result.scalar_one_or_none()

        return {
            "transaction_id": str(tx.id),
            "trade_type": tx.trade_type.value,
            "status": tx.status.value,
            "credits_amount": tx.credits_amount,
            "price_per_credit_usd": tx.price_per_credit_usd,
            "total_value_usd": tx.total_value_usd,
            "commission_rate": tx.commission_rate,
            "commission_usd": tx.commission_usd,
            "delivery_date": tx.delivery_date,
            "escrow": {
                "amount_usd": escrow.amount_usd if escrow else None,
                "buyer_deposited": escrow.buyer_deposited if escrow else None,
                "seller_transferred": escrow.seller_transferred if escrow else None,
                "status": escrow.status if escrow else None,
            },
            "commission": {
                "invoiced": commission.invoiced if commission else None,
                "invoice_number": commission.invoice_number if commission else None,
            },
        }
