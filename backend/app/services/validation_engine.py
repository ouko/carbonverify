from datetime import datetime
from typing import Dict, Any, List, Optional

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from app.core.logging import get_logger

logger = get_logger(__name__)

# JSON Schemas for different data types
EXCEL_CSV_SCHEMA = {
    "type": "object",
    "properties": {
        "data": {"type": "array"},
        "total_rows": {"type": "integer", "minimum": 0},
        "valid_rows": {"type": "integer", "minimum": 0},
        "invalid_rows": {"type": "integer", "minimum": 0},
    },
    "required": ["data", "total_rows"],
}

PDF_SCHEMA = {
    "type": "object",
    "properties": {
        "num_pages": {"type": "integer", "minimum": 1},
        "document_type": {"type": "string"},
        "text_length": {"type": "integer", "minimum": 0},
    },
    "required": ["num_pages", "document_type"],
}

IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "width": {"type": "integer", "minimum": 1},
        "height": {"type": "integer", "minimum": 1},
        "format": {"type": "string"},
        "category": {"type": "string"},
    },
    "required": ["width", "height", "format"],
}

IOT_SCHEMA = {
    "type": "object",
    "properties": {
        "normalized": {"type": "object"},
        "is_valid": {"type": "boolean"},
    },
    "required": ["normalized", "is_valid"],
}

SCHEMA_MAP = {
    "excel": EXCEL_CSV_SCHEMA,
    "csv": EXCEL_CSV_SCHEMA,
    "pdf": PDF_SCHEMA,
    "image": IMAGE_SCHEMA,
    "iot": IOT_SCHEMA,
}


def validate_json_schema(data: Dict[str, Any], data_type: str) -> List[str]:
    """Validate processed data against JSON Schema."""
    errors = []
    schema = SCHEMA_MAP.get(data_type)
    if not schema:
        errors.append(f"No JSON Schema defined for data type: {data_type}")
        return errors

    try:
        validate(instance=data, schema=schema)
    except JsonSchemaValidationError as e:
        errors.append(f"JSON Schema validation failed: {e.message}")
    except Exception as e:
        errors.append(f"Schema validation error: {str(e)}")

    return errors


def validate_gps_coordinates(lat: Optional[float], lon: Optional[float]) -> List[str]:
    """Validate GPS coordinates."""
    errors = []
    if lat is None or lon is None:
        errors.append("GPS coordinates are missing")
        return errors

    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if not (-90 <= lat_f <= 90):
            errors.append(f"Latitude {lat_f} out of range [-90, 90]")
        if not (-180 <= lon_f <= 180):
            errors.append(f"Longitude {lon_f} out of range [-180, 180]")
        if abs(lat_f) < 0.01 and abs(lon_f) < 0.01:
            errors.append("GPS coordinates appear invalid (near 0,0)")
    except (ValueError, TypeError):
        errors.append("GPS coordinates are not valid numbers")

    return errors


def validate_temporal_consistency(
    timestamps: List[datetime],
    monitoring_period_start: Optional[datetime] = None,
    monitoring_period_end: Optional[datetime] = None,
) -> List[str]:
    """Validate temporal consistency of data points."""
    errors = []
    if not timestamps:
        errors.append("No timestamps provided for temporal validation")
        return errors

    sorted_ts = sorted(timestamps)
    if len(sorted_ts) >= 2:
        # Check for future dates
        now = datetime.utcnow()
        for ts in sorted_ts:
            if ts > now:
                errors.append(f"Timestamp {ts.isoformat()} is in the future")

        # Check for data outside monitoring period
        if monitoring_period_start:
            early = [ts for ts in sorted_ts if ts < monitoring_period_start]
            if early:
                errors.append(f"{len(early)} records before monitoring period start")

        if monitoring_period_end:
            late = [ts for ts in sorted_ts if ts > monitoring_period_end]
            if late:
                errors.append(f"{len(late)} records after monitoring period end")

        # Check for large gaps
        for i in range(1, len(sorted_ts)):
            gap_days = (sorted_ts[i] - sorted_ts[i - 1]).days
            if gap_days > 365:
                errors.append(
                    f"Large temporal gap of {gap_days} days between records"
                )

    return errors


def validate_cross_reference(
    primary_data: Dict[str, Any],
    reference_data: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Cross-reference validation between data sources."""
    errors = []
    if not reference_data:
        return errors

    # Example: check if stove_ids in primary data exist in reference
    primary_stoves = set()
    reference_stoves = set()

    if "data" in primary_data and isinstance(primary_data["data"], list):
        primary_stoves = {str(row.get("stove_id")) for row in primary_data["data"] if row.get("stove_id")}

    if "data" in reference_data and isinstance(reference_data["data"], list):
        reference_stoves = {str(row.get("stove_id")) for row in reference_data["data"] if row.get("stove_id")}

    if primary_stoves and reference_stoves:
        unknown = primary_stoves - reference_stoves
        if unknown:
            errors.append(f"{len(unknown)} stove IDs not found in reference data")

    return errors


def compute_confidence_score(
    data: Dict[str, Any],
    data_type: str,
    validation_errors: List[str],
    source_reliability: float = 1.0,
) -> float:
    """Compute confidence score (0-1) based on data quality."""
    score = 1.0

    # Deduct for validation errors
    error_penalty = min(len(validation_errors) * 0.1, 0.5)
    score -= error_penalty

    # Data completeness bonus/penalty
    if data_type in ("excel", "csv"):
        total = data.get("total_rows", 0)
        valid = data.get("valid_rows", 0)
        if total > 0:
            completeness = valid / total
            score = score * 0.7 + completeness * 0.3

    elif data_type == "pdf":
        text_len = data.get("text_length", 0)
        pages = data.get("num_pages", 1)
        if pages > 0:
            avg_text = text_len / pages
            if avg_text < 50:
                score -= 0.2  # Likely scanned/image PDF

    elif data_type == "image":
        if data.get("gps"):
            score += 0.05
        if data.get("timestamp"):
            score += 0.05
        if data.get("category") and data["category"] != "other":
            score += 0.05
        score = min(score, 1.0)

    elif data_type == "iot":
        normalized = data.get("normalized", {})
        filled_fields = sum(1 for f in ["stove_id", "timestamp", "cooking_events", "total_cooking_minutes"] if normalized.get(f))
        completeness = filled_fields / 4.0
        score = score * 0.6 + completeness * 0.4

    # Apply source reliability factor
    score *= source_reliability

    return max(0.0, min(1.0, round(score, 4)))


def run_full_validation(
    data: Dict[str, Any],
    data_type: str,
    project_confidence_threshold: float = 0.85,
    source_reliability: float = 1.0,
    monitoring_period_start: Optional[datetime] = None,
    monitoring_period_end: Optional[datetime] = None,
    reference_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run complete validation pipeline and return result."""
    all_errors = []

    # 1. JSON Schema validation
    schema_errors = validate_json_schema(data, data_type)
    all_errors.extend(schema_errors)

    # 2. Data-specific validation
    if data_type in ("excel", "csv"):
        all_errors.extend(data.get("validation_errors", []))

    elif data_type == "pdf":
        all_errors.extend(data.get("validation_errors", []))

    elif data_type == "image":
        all_errors.extend(data.get("validation_errors", []))

    elif data_type == "iot":
        all_errors.extend(data.get("validation_errors", []))
        all_errors.extend(data.get("anomalies", []))

    # 3. Temporal validation
    timestamps = []
    if data_type in ("excel", "csv") and "data" in data:
        for row in data["data"]:
            ts = row.get("timestamp_parsed") or row.get("timestamp")
            if ts:
                try:
                    if isinstance(ts, str):
                        timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                    elif isinstance(ts, datetime):
                        timestamps.append(ts)
                except ValueError:
                    pass

    if timestamps and (monitoring_period_start or monitoring_period_end):
        temporal_errors = validate_temporal_consistency(timestamps, monitoring_period_start, monitoring_period_end)
        all_errors.extend(temporal_errors)

    # 4. Cross-reference validation
    if reference_data:
        xref_errors = validate_cross_reference(data, reference_data)
        all_errors.extend(xref_errors)

    # 5. Compute confidence score
    confidence = compute_confidence_score(data, data_type, all_errors, source_reliability)

    # 6. Determine status
    if all_errors and confidence < project_confidence_threshold:
        status = "flagged"
    elif all_errors:
        status = "flagged"
    else:
        status = "valid"

    return {
        "status": status,
        "confidence_score": confidence,
        "validation_errors": all_errors,
        "needs_human_review": confidence < project_confidence_threshold,
    }
