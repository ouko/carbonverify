from datetime import datetime
from typing import Dict, Any, List

from app.core.logging import get_logger

logger = get_logger(__name__)

# Normalized schema fields
NORMALIZED_FIELDS = [
    "stove_id",
    "timestamp",
    "cooking_events",
    "total_cooking_minutes",
    "temperature_avg",
    "usage_status",
    "data_quality_flag",
]

# Known IoT provider field mappings
PROVIDER_MAPPINGS = {
    "koko_networks": {
        "stove_id": ["stove_id", "device_id", "stoveId"],
        "timestamp": ["timestamp", "ts", "recorded_at"],
        "cooking_events": ["cooking_events", "burns", "sessions"],
        "total_cooking_minutes": ["total_cooking_minutes", "cooking_minutes", "duration_min"],
        "temperature_avg": ["temperature_avg", "temp_avg", "avg_temp"],
        "usage_status": ["usage_status", "status", "operational_status"],
        "data_quality_flag": ["data_quality_flag", "quality", "signal_strength"],
    },
    "burn_manufacturing": {
        "stove_id": ["stove_id", "serial_number", "unit_id"],
        "timestamp": ["timestamp", "date", "recorded_at"],
        "cooking_events": ["cooking_events", "ignitions", "uses"],
        "total_cooking_minutes": ["total_cooking_minutes", "cook_time", "duration"],
        "temperature_avg": ["temperature_avg", "stove_temp", "avg_temperature"],
        "usage_status": ["usage_status", "state", "operational_state"],
        "data_quality_flag": ["data_quality_flag", "quality_flag", "rssi"],
    },
    "generic_gsm": {
        "stove_id": ["stove_id", "device_id", "id"],
        "timestamp": ["timestamp", "time", "datetime"],
        "cooking_events": ["cooking_events", "events", "count"],
        "total_cooking_minutes": ["total_cooking_minutes", "minutes", "cooking_time"],
        "temperature_avg": ["temperature_avg", "temperature", "temp"],
        "usage_status": ["usage_status", "status"],
        "data_quality_flag": ["data_quality_flag", "quality", "valid"],
    },
}


def detect_provider(payload: Dict[str, Any]) -> str:
    """Auto-detect IoT provider based on payload structure."""
    keys = set(k.lower() for k in payload.keys())

    if "koko" in keys or any("koko" in str(v).lower() for v in payload.values()):
        return "koko_networks"
    if "burn" in keys or any("burn" in str(v).lower() for v in payload.values()):
        return "burn_manufacturing"

    # Score based on field name matches
    scores = {}
    for provider, mapping in PROVIDER_MAPPINGS.items():
        score = 0
        for canonical, aliases in mapping.items():
            if any(alias.lower() in keys for alias in aliases):
                score += 1
        scores[provider] = score

    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "generic_gsm"


def normalize_payload(payload: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Normalize provider-specific payload to standard schema."""
    mapping = PROVIDER_MAPPINGS.get(provider, PROVIDER_MAPPINGS["generic_gsm"])
    normalized = {}

    for canonical_field, aliases in mapping.items():
        for alias in aliases:
            if alias in payload:
                normalized[canonical_field] = payload[alias]
                break
            # Try case-insensitive match
            for key in payload:
                if key.lower() == alias.lower():
                    normalized[canonical_field] = payload[key]
                    break
            if canonical_field in normalized:
                break

    # Include any unmapped fields in raw_payload
    normalized["raw_payload"] = payload
    normalized["detected_provider"] = provider
    return normalized


def validate_iot_data(normalized: Dict[str, Any]) -> List[str]:
    """Validate normalized IoT data."""
    errors = []

    # Check required fields
    if not normalized.get("stove_id"):
        errors.append("stove_id is missing")
    if not normalized.get("timestamp"):
        errors.append("timestamp is missing")

    # Validate timestamp
    ts = normalized.get("timestamp")
    if ts:
        try:
            if isinstance(ts, str):
                datetime.fromisoformat(ts.replace("Z", "+00:00"))
            elif not isinstance(ts, datetime):
                errors.append("timestamp has invalid type")
        except ValueError:
            errors.append("timestamp has invalid format")

    # Validate cooking metrics
    events = normalized.get("cooking_events")
    if events is not None:
        try:
            if int(events) < 0:
                errors.append("cooking_events cannot be negative")
            if int(events) > 100:
                errors.append("cooking_events suspiciously high (>100)")
        except (ValueError, TypeError):
            errors.append("cooking_events is not a valid integer")

    minutes = normalized.get("total_cooking_minutes")
    if minutes is not None:
        try:
            if float(minutes) < 0:
                errors.append("total_cooking_minutes cannot be negative")
            if float(minutes) > 1440:
                errors.append("total_cooking_minutes exceeds 24 hours")
        except (ValueError, TypeError):
            errors.append("total_cooking_minutes is not a valid number")

    temp = normalized.get("temperature_avg")
    if temp is not None:
        try:
            t = float(temp)
            if t < 0 or t > 500:
                errors.append(f"temperature_avg {t} out of realistic range [0, 500]")
        except (ValueError, TypeError):
            errors.append("temperature_avg is not a valid number")

    return errors


def detect_anomalies(normalized: Dict[str, Any]) -> List[str]:
    """Detect anomalies in IoT data for flagging."""
    anomalies = []

    minutes = normalized.get("total_cooking_minutes")
    events = normalized.get("cooking_events")

    if minutes is not None and events is not None:
        try:
            m = float(minutes)
            e = int(events)
            if e > 0 and m / e > 180:
                anomalies.append("Average cooking event duration > 3 hours")
            if e > 0 and m / e < 1:
                anomalies.append("Average cooking event duration < 1 minute")
            if e == 0 and m > 0:
                anomalies.append("Cooking minutes recorded with zero events")
        except (ValueError, TypeError):
            pass

    return anomalies


def process_iot_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process IoT webhook payload and return normalized result."""
    logger.info("processing_iot_webhook", payload_keys=list(payload.keys()))

    provider = detect_provider(payload)
    normalized = normalize_payload(payload, provider)
    validation_errors = validate_iot_data(normalized)
    anomalies = detect_anomalies(normalized)

    result = {
        "detected_provider": provider,
        "normalized": normalized,
        "validation_errors": validation_errors,
        "anomalies": anomalies,
        "is_valid": len(validation_errors) == 0,
        "has_anomalies": len(anomalies) > 0,
    }

    logger.info(
        "iot_webhook_processed",
        provider=provider,
        is_valid=result["is_valid"],
        has_anomalies=result["has_anomalies"],
    )
    return result
