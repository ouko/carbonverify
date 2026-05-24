"""Leakage Detector Module - Algorithmic checks for market, activity, and spatial leakage."""

import math
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def detect_market_leakage(
    project_area_fuel_prices: List[Dict[str, Any]],
    control_area_fuel_prices: List[Dict[str, Any]],
    price_metric: str = "wood_price_per_kg",
) -> Dict[str, Any]:
    """
    Detect market leakage via fuel price changes.

    If project area fuel prices drop significantly relative to control areas,
    it may indicate reduced demand spilling into other markets.
    """
    if not project_area_fuel_prices or not control_area_fuel_prices:
        return {
            "type": "market_leakage",
            "detected": False,
            "magnitude_tco2e": 0.0,
            "confidence": 0.0,
            "indicators": [],
            "mitigation_recommendation": "Collect price monitoring data",
        }

    # Calculate price trends
    project_prices = [p.get(price_metric, 0) for p in project_area_fuel_prices if p.get(price_metric)]
    control_prices = [p.get(price_metric, 0) for p in control_area_fuel_prices if p.get(price_metric)]

    if len(project_prices) < 2 or len(control_prices) < 2:
        return {
            "type": "market_leakage",
            "detected": False,
            "magnitude_tco2e": 0.0,
            "confidence": 0.3,
            "indicators": ["Insufficient price data for trend analysis"],
            "mitigation_recommendation": "Expand price monitoring to at least 2 time points",
        }

    project_change = (project_prices[-1] - project_prices[0]) / project_prices[0] if project_prices[0] else 0
    control_change = (control_prices[-1] - control_prices[0]) / control_prices[0] if control_prices[0] else 0

    relative_change = project_change - control_change

    indicators = []
    detected = False
    magnitude = 0.0
    confidence = 0.5

    if relative_change < -0.15:  # 15% drop relative to control
        detected = True
        indicators.append(f"Fuel price dropped {abs(relative_change)*100:.1f}% relative to control area")
        magnitude = abs(relative_change) * 0.10  # Simplified: 10% of price change as leakage proxy
        confidence = min(0.90, 0.50 + abs(relative_change))
    elif relative_change < -0.05:
        indicators.append(f"Fuel price dropped {abs(relative_change)*100:.1f}% relative to control (moderate)")
        confidence = 0.40 + abs(relative_change)

    return {
        "type": "market_leakage",
        "detected": detected,
        "magnitude_tco2e": round(magnitude, 4),
        "confidence": round(confidence, 4),
        "indicators": indicators,
        "data_summary": {
            "project_price_change_pct": round(project_change * 100, 2),
            "control_price_change_pct": round(control_change * 100, 2),
            "relative_change_pct": round(relative_change * 100, 2),
        },
        "mitigation_recommendation": (
            "Monitor cross-border fuel sales; consider buffer of 10-15% if price drop >20%"
            if detected else
            "Continue quarterly price monitoring"
        ),
    }


def detect_activity_shifting(
    household_stove_usage: List[Dict[str, Any]],
    min_usage_days: int = 30,
) -> Dict[str, Any]:
    """
    Detect activity-shifting leakage (stove stacking).

    Analyzes whether households continue using baseline stoves alongside
    improved stoves, reducing net emission reductions.
    """
    if not household_stove_usage:
        return {
            "type": "activity_shifting",
            "detected": False,
            "magnitude_tco2e": 0.0,
            "confidence": 0.0,
            "indicators": [],
            "mitigation_recommendation": "Collect stove usage monitoring data",
        }

    stacking_count = 0
    total_households = len(household_stove_usage)
    baseline_continued_fractions = []

    for household in household_stove_usage:
        usage_events = household.get("usage_events", [])
        if len(usage_events) < min_usage_days:
            continue

        # Check if baseline stove still used
        baseline_events = [e for e in usage_events if e.get("stove_type") == "baseline"]
        improved_events = [e for e in usage_events if e.get("stove_type") == "improved"]

        total_events = len(baseline_events) + len(improved_events)
        if total_events == 0:
            continue

        baseline_fraction = len(baseline_events) / total_events
        baseline_continued_fractions.append(baseline_fraction)

        if baseline_fraction > 0.20:  # >20% continued baseline use = stacking
            stacking_count += 1

    if not baseline_continued_fractions:
        return {
            "type": "activity_shifting",
            "detected": False,
            "magnitude_tco2e": 0.0,
            "confidence": 0.3,
            "indicators": ["Insufficient usage data"],
            "mitigation_recommendation": "Deploy SUMs or increase survey frequency",
        }

    avg_baseline_fraction = sum(baseline_continued_fractions) / len(baseline_continued_fractions)
    stacking_rate = stacking_count / total_households if total_households > 0 else 0

    detected = False
    magnitude = 0.0
    confidence = 0.5
    indicators = []

    if stacking_rate > 0.30:
        detected = True
        magnitude = avg_baseline_fraction * 0.8  # Simplified: baseline use reduces net reductions
        confidence = min(0.90, 0.50 + stacking_rate)
        indicators.append(f"{stacking_rate*100:.1f}% of households exhibit stove stacking (>30% baseline use)")
    elif stacking_rate > 0.10:
        indicators.append(f"{stacking_rate*100:.1f}% of households show moderate stove stacking")
        confidence = 0.40 + stacking_rate

    if avg_baseline_fraction > 0.15:
        indicators.append(f"Average baseline stove usage: {avg_baseline_fraction*100:.1f}% of cooking events")

    return {
        "type": "activity_shifting",
        "detected": detected,
        "magnitude_tco2e": round(magnitude, 4),
        "confidence": round(confidence, 4),
        "indicators": indicators,
        "data_summary": {
            "households_analyzed": total_households,
            "stacking_households": stacking_count,
            "stacking_rate": round(stacking_rate, 4),
            "avg_baseline_fraction": round(avg_baseline_fraction, 4),
        },
        "mitigation_recommendation": (
            "Implement user training programs; consider 15-20% buffer for issuance"
            if detected else
            "Continue monitoring; maintain user engagement programs"
        ),
    }


def detect_spatial_leakage(
    stove_installations: List[Dict[str, Any]],
    project_boundary: List[List[float]],
    buffer_km: float = 5.0,
) -> Dict[str, Any]:
    """
    Detect spatial leakage: stoves installed outside project boundary.

    Uses simple bounding box check. In production, use Shapely for proper polygon containment.
    """
    if not stove_installations or not project_boundary:
        return {
            "type": "spatial_leakage",
            "detected": False,
            "magnitude_tco2e": 0.0,
            "confidence": 0.0,
            "indicators": [],
            "mitigation_recommendation": "Collect GPS coordinates for all installations",
        }

    # Simple bounding box from boundary
    lats = [p[1] for p in project_boundary]
    lons = [p[0] for p in project_boundary]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Expand by buffer (approximate: 1 degree ~ 111km)
    lat_buffer = buffer_km / 111.0
    lon_buffer = buffer_km / (111.0 * abs(math.cos(math.radians((min_lat + max_lat) / 2))))

    outside_count = 0
    total_count = len(stove_installations)

    for stove in stove_installations:
        lat = stove.get("gps_latitude")
        lon = stove.get("gps_longitude")
        if lat is None or lon is None:
            continue

        if not (min_lat - lat_buffer <= lat <= max_lat + lat_buffer and
                min_lon - lon_buffer <= lon <= max_lon + lon_buffer):
            outside_count += 1

    outside_rate = outside_count / total_count if total_count > 0 else 0

    detected = outside_rate > 0.05  # >5% outside boundary
    magnitude = outside_rate * 0.5 if detected else 0.0
    confidence = min(0.90, 0.50 + outside_rate * 5)

    indicators = []
    if outside_count > 0:
        indicators.append(f"{outside_count} stoves ({outside_rate*100:.1f}%) installed outside project boundary + {buffer_km}km buffer")

    return {
        "type": "spatial_leakage",
        "detected": detected,
        "magnitude_tco2e": round(magnitude, 4),
        "confidence": round(confidence, 4),
        "indicators": indicators,
        "data_summary": {
            "total_installations": total_count,
            "outside_boundary": outside_count,
            "outside_rate": round(outside_rate, 4),
        },
        "mitigation_recommendation": (
            "Verify eligibility of out-of-area stoves; exclude from crediting if not justified"
            if detected else
            "GPS tracking adequate; maintain verification protocols"
        ),
    }


def assess_leakage(
    price_data: Optional[List[Dict[str, Any]]] = None,
    usage_data: Optional[List[Dict[str, Any]]] = None,
    installation_data: Optional[List[Dict[str, Any]]] = None,
    project_boundary: Optional[List[List[float]]] = None,
    baseline_emissions_tco2e: float = 0.0,
) -> Dict[str, Any]:
    """
    Run full leakage assessment across all three types.

    Returns consolidated leakage assessment with total magnitude.
    """
    assessments = []

    # Market leakage
    market = detect_market_leakage(
        price_data or [],
        []  # Control area data would come from external source
    )
    assessments.append(market)

    # Activity shifting
    activity = detect_activity_shifting(usage_data or [])
    assessments.append(activity)

    # Spatial leakage
    spatial = detect_spatial_leakage(installation_data or [], project_boundary or [])
    assessments.append(spatial)

    # Total leakage
    total_magnitude = sum(a["magnitude_tco2e"] for a in assessments)
    avg_confidence = sum(a["confidence"] for a in assessments) / len(assessments) if assessments else 0

    # Cap leakage at 30% of baseline
    max_leakage = baseline_emissions_tco2e * 0.30
    capped_magnitude = min(total_magnitude, max_leakage)

    return {
        "leakage_types": assessments,
        "total_leakage_tco2e": round(capped_magnitude, 4),
        "uncapped_leakage_tco2e": round(total_magnitude, 4),
        "leakage_as_pct_of_baseline": round((capped_magnitude / baseline_emissions_tco2e * 100) if baseline_emissions_tco2e > 0 else 0, 2),
        "overall_confidence": round(avg_confidence, 4),
        "buffer_recommendation_pct": round(min(30.0, total_magnitude * 100 + 5), 1),
    }
