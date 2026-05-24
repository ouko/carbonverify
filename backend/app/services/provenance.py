import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def hash_data(data: Dict[str, Any]) -> str:
    """Create deterministic SHA-256 hash of data."""
    canonical = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_provenance_record(
    raw_source: str,
    extraction_method: str,
    original_filename: Optional[str] = None,
    file_hash: Optional[str] = None,
    transformations: Optional[List[Dict[str, Any]]] = None,
    validation_result: Optional[Dict[str, Any]] = None,
    parent_hash: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a provenance record with hash chain for integrity verification."""
    record = {
        "raw_source": raw_source,
        "extraction_method": extraction_method,
        "original_filename": original_filename,
        "file_hash": file_hash,
        "transformations": transformations or [],
        "validation_result": validation_result,
        "parent_hash": parent_hash,
        "metadata": metadata or {},
        "storage_timestamp": datetime.utcnow().isoformat(),
    }

    # Compute hash of this record for chain integrity
    record_hash = hash_data(record)
    record["record_hash"] = record_hash

    return record


def add_transformation(
    provenance: Dict[str, Any],
    step: str,
    description: str,
    input_hash: Optional[str] = None,
    output_data: Optional[Dict[str, Any]] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a transformation step to the provenance chain."""
    transformation = {
        "step": step,
        "description": description,
        "timestamp": datetime.utcnow().isoformat(),
        "input_hash": input_hash or provenance.get("record_hash"),
        "output_hash": hash_data(output_data) if output_data else None,
        "parameters": parameters or {},
    }

    provenance["transformations"].append(transformation)
    # Recompute record hash after adding transformation
    provenance["record_hash"] = hash_data(provenance)
    provenance["previous_hash"] = provenance.get("record_hash")

    return provenance


def verify_chain_integrity(provenance: Dict[str, Any]) -> bool:
    """Verify the integrity of a provenance record by checking its hash."""
    stored_hash = provenance.get("record_hash")
    if not stored_hash:
        return False

    # Create copy without record_hash to recompute
    check = {k: v for k, v in provenance.items() if k != "record_hash"}
    computed_hash = hash_data(check)

    return computed_hash == stored_hash


def build_full_provenance(
    file_bytes: Optional[bytes] = None,
    original_filename: Optional[str] = None,
    detected_type: Optional[str] = None,
    processing_pipeline: Optional[str] = None,
    processing_result: Optional[Dict[str, Any]] = None,
    validation_result: Optional[Dict[str, Any]] = None,
    s3_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a complete provenance record from upload through validation."""
    file_hash = None
    if file_bytes:
        file_hash = hashlib.sha256(file_bytes).hexdigest()

    provenance = create_provenance_record(
        raw_source=s3_key or original_filename or "unknown",
        extraction_method=processing_pipeline or "unknown",
        original_filename=original_filename,
        file_hash=file_hash,
        validation_result=validation_result,
        metadata={
            "detected_type": detected_type,
            "s3_key": s3_key,
        },
    )

    if processing_result:
        provenance = add_transformation(
            provenance,
            step="processing",
            description=f"Processed via {processing_pipeline}",
            output_data=processing_result,
        )

    if validation_result:
        provenance = add_transformation(
            provenance,
            step="validation",
            description="Ran validation engine",
            output_data=validation_result,
        )

    return provenance
