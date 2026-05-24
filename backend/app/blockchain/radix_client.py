"""
Radix DLT client for CarbonVerify audit trail anchoring.

Uses the Radix Babylon Gateway API to submit and verify transactions
containing hashed audit data. In production, this should use a proper
Radix wallet connector or a dedicated signer service.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RadixAnchorResult:
    """Result of anchoring data to the Radix ledger."""

    def __init__(
        self,
        success: bool,
        tx_ref: Optional[str] = None,
        data_hash: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.tx_ref = tx_ref
        self.data_hash = data_hash
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.error = error


class RadixClient:
    """
    Client for interacting with the Radix DLT network.

    In development mode (RADIX_ENABLED=False), transactions are simulated
    and tx_refs are generated as deterministic UUIDs from the data hash.
    """

    def __init__(self):
        self.gateway_url = settings.RADIX_GATEWAY_URL
        self.network_id = settings.RADIX_NETWORK_ID
        self.account_address = settings.RADIX_ACCOUNT_ADDRESS
        self.enabled = settings.RADIX_ENABLED
        self._client = httpx.AsyncClient(timeout=30.0)

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of canonical JSON data."""
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _build_manifest(self, data_hash: str, memo: str) -> str:
        """
        Build a Radix transaction manifest that stores a hash.

        In Radix, manifests describe the transaction intent. This simplified
        manifest calls a metadata component to store the hash. In production,
        you would deploy a dedicated CarbonVerify audit component.
        """
        return f"""CALL_METHOD
    Address("{self.account_address}")
    "lock_fee"
    Decimal("1");

# Store audit hash in transaction manifest metadata
# Hash: {data_hash}
# Memo: {memo}
# Timestamp: {datetime.now(timezone.utc).isoformat()}

CALL_METHOD
    Address("{self.account_address}")
    "deposit_batch"
    Expression("ENTIRE_WORKTOP");
"""

    async def anchor_audit_log(
        self,
        audit_data: Dict[str, Any],
        memo: str = "CarbonVerify Audit",
    ) -> RadixAnchorResult:
        """
        Anchor an audit log entry to the Radix ledger.

        Returns a RadixAnchorResult containing the transaction reference.
        """
        data_hash = self._compute_hash(audit_data)

        if not self.enabled:
            # Development mode: simulate anchoring with deterministic UUID
            simulated_tx = str(uuid.uuid5(uuid.NAMESPACE_OID, data_hash))
            logger.info("radix_anchor_simulated", data_hash=data_hash, tx_ref=simulated_tx)
            return RadixAnchorResult(
                success=True,
                tx_ref=simulated_tx,
                data_hash=data_hash,
                timestamp=datetime.now(timezone.utc),
            )

        try:
            manifest = self._build_manifest(data_hash, memo)

            # Submit transaction intent to Radix Gateway
            # In production, this requires proper transaction signing
            payload = {
                "network_identifier": {"network": "mainnet" if self.network_id == 1 else "stokenet"},
                "transaction": {
                    "manifest": manifest,
                    "message": f"CV:{data_hash[:16]}",
                },
            }

            response = await self._client.post(
                f"{self.gateway_url}/transaction/submit",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            tx_ref = result.get("transaction_identifier", {}).get("hash")
            logger.info("radix_anchor_success", tx_ref=tx_ref, data_hash=data_hash)
            return RadixAnchorResult(
                success=True,
                tx_ref=tx_ref,
                data_hash=data_hash,
                timestamp=datetime.now(timezone.utc),
            )

        except httpx.HTTPStatusError as exc:
            logger.error("radix_anchor_http_error", status=exc.response.status_code, detail=str(exc))
            return RadixAnchorResult(success=False, data_hash=data_hash, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.error("radix_anchor_error", error=str(exc))
            return RadixAnchorResult(success=False, data_hash=data_hash, error=str(exc))

    async def verify_anchor(
        self,
        tx_ref: str,
        expected_data: Dict[str, Any],
    ) -> bool:
        """
        Verify that the data on the ledger matches the expected data.

        Queries the Radix Gateway for the transaction and recomputes the hash.
        """
        expected_hash = self._compute_hash(expected_data)

        if not self.enabled:
            # Development mode: verify against deterministic UUID
            expected_tx = str(uuid.uuid5(uuid.NAMESPACE_OID, expected_hash))
            return expected_tx == tx_ref

        try:
            response = await self._client.post(
                f"{self.gateway_url}/transaction/committed-details",
                json={
                    "network_identifier": {"network": "mainnet" if self.network_id == 1 else "stokenet"},
                    "transaction_identifier": {"hash": tx_ref},
                },
            )
            response.raise_for_status()
            result = response.json()

            # Extract message from transaction metadata
            message = result.get("transaction", {}).get("message", "")
            # Hash is embedded in the message as CV:hash_prefix
            if expected_hash[:16] in message:
                logger.info("radix_verify_success", tx_ref=tx_ref)
                return True

            logger.warning("radix_verify_hash_mismatch", tx_ref=tx_ref)
            return False

        except Exception as exc:
            logger.error("radix_verify_error", tx_ref=tx_ref, error=str(exc))
            return False

    async def get_transaction_status(self, tx_ref: str) -> Dict[str, Any]:
        """Get the status of a Radix transaction."""
        if not self.enabled:
            return {"status": "simulated", "tx_ref": tx_ref}

        try:
            response = await self._client.post(
                f"{self.gateway_url}/transaction/committed-details",
                json={
                    "network_identifier": {"network": "mainnet" if self.network_id == 1 else "stokenet"},
                    "transaction_identifier": {"hash": tx_ref},
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def close(self):
        await self._client.aclose()


class AuditTrailAnchor:
    """High-level service for anchoring CarbonVerify audit events to Radix."""

    def __init__(self):
        self.client = RadixClient()

    async def anchor_calculation_run(
        self,
        calculation_run_id: uuid.UUID,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
    ) -> RadixAnchorResult:
        """Anchor a calculation run to the ledger."""
        audit_data = {
            "type": "calculation_run",
            "id": str(calculation_run_id),
            "input_hash": hashlib.sha256(json.dumps(input_data, sort_keys=True, default=str).encode()).hexdigest(),
            "output_hash": hashlib.sha256(json.dumps(output_data, sort_keys=True, default=str).encode()).hexdigest(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await self.client.anchor_audit_log(audit_data, memo=f"Calc:{calculation_run_id}")

    async def anchor_report_approval(
        self,
        report_id: uuid.UUID,
        approver_id: uuid.UUID,
        report_hash: str,
    ) -> RadixAnchorResult:
        """Anchor a report approval to the ledger."""
        audit_data = {
            "type": "report_approved",
            "report_id": str(report_id),
            "approver_id": str(approver_id),
            "report_hash": report_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await self.client.anchor_audit_log(audit_data, memo=f"Report:{report_id}")

    async def anchor_data_change(
        self,
        target_type: str,
        target_id: uuid.UUID,
        previous_hash: str,
        new_hash: str,
        actor_id: uuid.UUID,
    ) -> RadixAnchorResult:
        """Anchor any data change to the ledger."""
        audit_data = {
            "type": "data_change",
            "target_type": target_type,
            "target_id": str(target_id),
            "previous_hash": previous_hash,
            "new_hash": new_hash,
            "actor_id": str(actor_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await self.client.anchor_audit_log(audit_data, memo=f"Change:{target_type}:{target_id}")

    async def verify(self, tx_ref: str, expected_data: Dict[str, Any]) -> bool:
        """Verify an anchored transaction."""
        return await self.client.verify_anchor(tx_ref, expected_data)
