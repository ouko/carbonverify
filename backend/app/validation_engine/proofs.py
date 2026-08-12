"""Cryptographic proof generation with Merkle trees and Radix anchoring."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.validation_engine.models import (
    ProofType,
    ValidationProof,
    ValidationRun,
    ValidationStepExecution,
)
from app.validation_engine.schemas import WorkflowStep, WorkflowStepType
from app.services.s3 import upload_bytes


PROOF_S3_THRESHOLD_BYTES = 100 * 1024  # 100 KB


def _upload_proof_to_s3(data: dict, run_id: str) -> str:
    """Upload proof data to S3 and return the S3 key."""
    s3_key = f"proofs/{run_id}/{uuid.uuid4()}.json"
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    upload_bytes(payload, s3_key, content_type="application/json")
    return s3_key


def _canonical_json(data: Any) -> str:
    """Canonical JSON for deterministic hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


class MerkleNode:
    """A node in a Merkle tree."""

    __slots__ = ("hash", "left", "right", "leaf_index", "is_leaf")

    def __init__(
        self,
        hash_value: str,
        left: Optional["MerkleNode"] = None,
        right: Optional["MerkleNode"] = None,
        leaf_index: Optional[int] = None,
    ):
        self.hash = hash_value
        self.left = left
        self.right = right
        self.leaf_index = leaf_index
        self.is_leaf = left is None and right is None


class MerkleTree:
    """SHA-256 based Merkle tree for proof chaining."""

    def __init__(self, leaves: List[str]):
        if not leaves:
            raise ValueError("Merkle tree requires at least one leaf")
        self.leaves = leaves
        self.root, self._leaf_nodes = self._build(leaves)

    def _build(self, hashes: List[str]) -> Tuple[MerkleNode, List[MerkleNode]]:
        """Build the tree bottom-up."""
        # Create leaf nodes
        leaf_nodes = [
            MerkleNode(h, leaf_index=i) for i, h in enumerate(hashes)
        ]
        current_level = leaf_nodes[:]

        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                combined = hashlib.sha256(
                    (left.hash + right.hash).encode("utf-8")
                ).hexdigest()
                next_level.append(MerkleNode(combined, left, right))
            current_level = next_level

        return current_level[0], leaf_nodes

    def get_root(self) -> str:
        return self.root.hash

    def get_proof_path(self, leaf_index: int) -> List[Dict[str, Any]]:
        """Get the Merkle proof path for a leaf.

        Returns a list of dicts with sibling_hash and is_right (True if our
        node is the right sibling, meaning sibling is on the left).
        """
        path = []
        idx = leaf_index
        current_level = [n.hash for n in self._leaf_nodes]

        while len(current_level) > 1:
            # If odd number of nodes, duplicate the last one
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])

            sibling_idx = idx ^ 1  # Flip last bit to get sibling
            is_right = idx % 2 == 1  # True if our node is the right sibling
            path.append({
                "sibling_hash": current_level[sibling_idx],
                "is_right": is_right,
            })

            # Build next level
            next_level = []
            for i in range(0, len(current_level), 2):
                combined = hashlib.sha256(
                    (current_level[i] + current_level[i + 1]).encode("utf-8")
                ).hexdigest()
                next_level.append(combined)

            current_level = next_level
            idx //= 2

        return path

    def verify_leaf(self, leaf_hash: str, leaf_index: int, proof_path: List[Dict[str, Any]]) -> bool:
        """Verify a leaf hash against the root using a proof path."""
        current = leaf_hash
        for step in proof_path:
            sibling = step["sibling_hash"]
            if step["is_right"]:
                # We are the right sibling, so sibling goes first
                current = hashlib.sha256((sibling + current).encode("utf-8")).hexdigest()
            else:
                # We are the left sibling, so we go first
                current = hashlib.sha256((current + sibling).encode("utf-8")).hexdigest()
        return current == self.root.hash


class ProofGenerator:
    """Generates and manages cryptographic proofs for validation runs."""

    def __init__(self):
        self._radix_client = None  # Lazy init

    async def capture_step_proof(
        self,
        db: AsyncSession,
        run: ValidationRun,
        step_exec: ValidationStepExecution,
        step: WorkflowStep,
    ) -> ValidationProof:
        """Capture proof artifacts for a step execution."""
        proof_data = {
            "step_id": step.id,
            "step_name": step.name,
            "step_type": step.type.value,
            "run_id": str(run.id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_snapshot": step_exec.input_payload,
            "output_snapshot": step_exec.output_payload,
            "step_hash": step_exec.step_hash,
        }

        # Add type-specific proof data
        if step.type == WorkflowStepType.http_request:
            proof_data["http_proof"] = await self._capture_http_proof(step_exec)
        elif step.type == WorkflowStepType.database_query:
            proof_data["db_proof"] = await self._capture_db_proof(step_exec)
        elif step.type == WorkflowStepType.dom_capture:
            proof_data["dom_proof"] = await self._capture_dom_proof(step_exec)
        elif step.type == WorkflowStepType.service_call:
            proof_data["service_proof"] = await self._capture_service_proof(step_exec)
        elif step.type == WorkflowStepType.external_api:
            proof_data["api_proof"] = await self._capture_external_api_proof(step_exec)

        canonical = _canonical_json(proof_data)
        proof_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        proof_size_bytes = len(canonical.encode("utf-8"))

        # Offload to S3 if proof data exceeds threshold
        if proof_size_bytes > PROOF_S3_THRESHOLD_BYTES:
            s3_key = _upload_proof_to_s3(proof_data, str(run.id))
            proof_data = {"s3_key": s3_key}

        proof = ValidationProof(
            run_id=run.id,
            step_execution_id=step_exec.id,
            proof_type=ProofType.http_request if step.type == WorkflowStepType.http_request else ProofType.service_output,
            proof_data=proof_data,
            proof_hash=proof_hash,
            proof_size_bytes=proof_size_bytes,
        )
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        return proof

    async def _capture_http_proof(self, step_exec: ValidationStepExecution) -> Dict[str, Any]:
        """Capture HTTP-specific proof data."""
        output = step_exec.output_payload or {}
        return {
            "request_url": output.get("url"),
            "request_method": output.get("method"),
            "response_status": output.get("status_code"),
            "response_headers": output.get("response_headers", {}),
            "response_body_hash": hashlib.sha256(
                str(output.get("response_body", "")).encode("utf-8")
            ).hexdigest() if output.get("response_body") else None,
            "latency_ms": output.get("latency_ms"),
        }

    async def _capture_db_proof(self, step_exec: ValidationStepExecution) -> Dict[str, Any]:
        """Capture database query proof data."""
        output = step_exec.output_payload or {}
        rows = output.get("rows", [])
        return {
            "query": output.get("query"),
            "row_count": len(rows),
            "rows_hash": hashlib.sha256(
                _canonical_json(rows).encode("utf-8")
            ).hexdigest() if rows else None,
            "execution_time_ms": output.get("execution_time_ms"),
        }

    async def _capture_dom_proof(self, step_exec: ValidationStepExecution) -> Dict[str, Any]:
        """Capture DOM snapshot proof data."""
        output = step_exec.output_payload or {}
        return {
            "url": output.get("url"),
            "title": output.get("title"),
            "viewport": output.get("viewport"),
            "html_hash": hashlib.sha256(
                str(output.get("html", "")).encode("utf-8")
            ).hexdigest() if output.get("html") else None,
            "screenshot_present": output.get("screenshot") is not None,
        }

    async def _capture_service_proof(self, step_exec: ValidationStepExecution) -> Dict[str, Any]:
        """Capture service call proof data."""
        output = step_exec.output_payload or {}
        return {
            "service_name": output.get("service_name"),
            "method_name": output.get("method_name"),
            "result_hash": hashlib.sha256(
                _canonical_json(output.get("result")).encode("utf-8")
            ).hexdigest() if output.get("result") is not None else None,
            "exception_present": output.get("exception") is not None,
        }

    async def _capture_external_api_proof(self, step_exec: ValidationStepExecution) -> Dict[str, Any]:
        """Capture external API proof data."""
        output = step_exec.output_payload or {}
        return {
            "provider": output.get("provider"),
            "endpoint": output.get("endpoint"),
            "status_code": output.get("status_code"),
            "response_hash": hashlib.sha256(
                str(output.get("response_body", "")).encode("utf-8")
            ).hexdigest() if output.get("response_body") else None,
        }

    async def build_merkle_tree(self, db: AsyncSession, run: ValidationRun) -> str:
        """Build a Merkle tree from all proofs in a run and store the root."""
        result = await db.execute(
            select(ValidationProof)
            .where(ValidationProof.run_id == run.id)
            .order_by(ValidationProof.captured_at)
        )
        proofs = list(result.scalars().all())

        if not proofs:
            # No proofs — hash the run metadata as single leaf
            leaf = hashlib.sha256(
                _canonical_json({
                    "run_id": str(run.id),
                    "workflow_id": str(run.workflow_id),
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "status": run.status.value,
                }).encode("utf-8")
            ).hexdigest()
            leaves = [leaf]
        else:
            leaves = [p.proof_hash for p in proofs]

        tree = MerkleTree(leaves)
        root = tree.get_root()

        # Update proof leaf indices
        for i, proof in enumerate(proofs):
            proof.merkle_leaf_index = i

        run.merkle_root = root
        await db.commit()
        return root

    async def anchor_to_radix(self, db: AsyncSession, run: ValidationRun) -> Optional[str]:
        """Anchor the Merkle root to the Radix ledger.

        Returns the transaction reference if successful, None otherwise.
        """
        if not run.merkle_root:
            await self.build_merkle_tree(db, run)

        # Lazy init Radix client
        if self._radix_client is None:
            from app.blockchain.radix_client import get_radix_client
            self._radix_client = get_radix_client()

        try:
            # Build the anchor payload
            anchor_payload = {
                "merkle_root": run.merkle_root,
                "run_id": str(run.id),
                "workflow_id": str(run.workflow_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "proof-v1",
            }

            # Submit to Radix (using the existing blockchain client)
            anchor_result = await self._radix_client.anchor_audit_log(
                audit_data=anchor_payload,
                memo=f"validation_proof:{str(run.id)}",
            )
            if not anchor_result.success:
                raise RuntimeError(f"Radix anchoring failed: {anchor_result.error}")
            tx_ref = anchor_result.tx_ref

            run.radix_tx_ref = tx_ref
            await db.commit()

            # Also store a radix_anchor proof
            proof = ValidationProof(
                run_id=run.id,
                step_execution_id=None,
                proof_type=ProofType.radix_anchor,
                proof_data={
                    "tx_ref": tx_ref,
                    "merkle_root": run.merkle_root,
                    "anchored_at": datetime.now(timezone.utc).isoformat(),
                },
                proof_hash=hashlib.sha256(
                    (run.merkle_root + tx_ref).encode("utf-8")
                ).hexdigest(),
            )
            db.add(proof)
            await db.commit()

            return tx_ref

        except Exception as exc:
            # Log but don't fail the run — proof is still valid locally
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Radix anchoring failed for run {run.id}: {exc}")
            return None

    def generate_certificate(self, run: ValidationRun, proofs: List[ValidationProof]) -> Dict[str, Any]:
        """Generate a proof certificate for external verification."""
        step_hashes = []
        for proof in proofs:
            proof_type_val = proof.proof_type.value if hasattr(proof.proof_type, "value") else proof.proof_type
            step_hashes.append({
                "proof_id": str(proof.id),
                "proof_type": proof_type_val,
                "proof_hash": proof.proof_hash,
                "merkle_leaf_index": proof.merkle_leaf_index,
            })

        cert_payload = {
            "run_id": str(run.id),
            "workflow_id": str(run.workflow_id),
            "workflow_name": None,  # Filled by caller if available
            "workflow_version": None,
            "merkle_root": run.merkle_root,
            "radix_tx_ref": run.radix_tx_ref,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "step_count": len(step_hashes),
            "proof_count": len(proofs),
            "step_hashes": step_hashes,
            "certificate_version": "v1",
        }

        cert_hash = hashlib.sha256(
            _canonical_json(cert_payload).encode("utf-8")
        ).hexdigest()
        cert_payload["certificate_hash"] = cert_hash

        return cert_payload
