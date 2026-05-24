"""fNRB (fraction of Non-Renewable Biomass) Calculator Module."""

import math
from typing import Dict, Any, Optional, Tuple

from app.calculations.constants import (
    fNRB_REFERENCE_POINTS as DEFAULT_REFERENCE_POINTS,
    CCP_FNRB_CAP,
    DEFAULT_FNRB,
    DEFAULT_FNRB_UNCERTAINTY,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in km between two lat/lon points."""
    R = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def spatial_interpolation(
    target_lat: float,
    target_lon: float,
    reference_points: Optional[Dict[Tuple[float, float], Dict[str, Any]]] = None,
    max_distance_km: float = 500.0,
    min_points: int = 1,
) -> Tuple[float, float, str]:
    """
    Inverse-distance weighted interpolation of fNRB from reference points.
    Returns (fnrb, uncertainty, source_description).
    """
    if reference_points is None:
        reference_points = DEFAULT_REFERENCE_POINTS

    distances = []
    for (ref_lat, ref_lon), data in reference_points.items():
        dist = haversine_distance(target_lat, target_lon, ref_lat, ref_lon)
        if dist <= max_distance_km:
            distances.append((dist, data))

    if len(distances) < min_points:
        logger.warning(
            "insufficient_reference_points",
            target_lat=target_lat,
            target_lon=target_lon,
            found=len(distances),
            required=min_points,
        )
        return DEFAULT_FNRB, DEFAULT_FNRB_UNCERTAINTY, "default_value"

    # Sort by distance
    distances.sort(key=lambda x: x[0])
    used_points = distances[:min(5, len(distances))]  # Use up to 5 nearest

    # IDW with power=2
    numerator = 0.0
    denom = 0.0
    weighted_uncertainty = 0.0
    sources = []

    for dist, data in used_points:
        if dist < 1.0:  # Very close to reference point
            return data["fnrb"], data["uncertainty"], f"direct_reference:{data['source']}"

        w = 1.0 / (dist ** 2)
        numerator += w * data["fnrb"]
        denom += w
        weighted_uncertainty += w * data["uncertainty"]
        sources.append(data["source"])

    interpolated_fnrb = numerator / denom
    interpolated_uncertainty = weighted_uncertainty / denom

    # Add distance penalty to uncertainty
    avg_dist = sum(d for d, _ in used_points) / len(used_points)
    distance_penalty = min(avg_dist / 1000.0, 0.10)  # Up to +0.10 for distant interpolation
    interpolated_uncertainty = math.sqrt(interpolated_uncertainty ** 2 + distance_penalty ** 2)

    source_desc = f"spatial_interpolation:{';'.join(set(sources))}"
    return interpolated_fnrb, interpolated_uncertainty, source_desc


def run_mofuss_simplified(lat: float, lon: float, fuel_type: str, assessment_year: int) -> Optional[Dict[str, Any]]:
    """
    Execute simplified MoFuSS model or return None if unavailable.
    This is a placeholder for actual MoFuSS integration.
    """
    # In a production system, this would call MoFuSS API or execute R/Python model
    # For now, we return None to trigger fallback to spatial interpolation
    logger.info("mofuss_placeholder", lat=lat, lon=lon, fuel_type=fuel_type, year=assessment_year)
    return None


def calculate_fnrb(
    project_location: Tuple[float, float],
    assessment_year: int,
    fuel_type: str,
    use_mofuss: bool = True,
) -> Dict[str, Any]:
    """
    Calculate fNRB for a cookstove project.

    Args:
        project_location: (latitude, longitude)
        assessment_year: Year of assessment
        fuel_type: wood, charcoal, biogas, lpg, ethanol, etc.
        use_mofuss: Whether to attempt MoFuSS model execution

    Returns:
        Dict with fNRB_value, uncertainty_range, source_reference, confidence_score, flags
    """
    lat, lon = project_location
    flags = []

    # Step 1: Try MoFuSS if requested
    mofuss_result = None
    if use_mofuss:
        mofuss_result = run_mofuss_simplified(lat, lon, fuel_type, assessment_year)

    if mofuss_result:
        fnrb = mofuss_result["fnrb"]
        uncertainty = mofuss_result["uncertainty"]
        source = f"mofuss_model:{mofuss_result.get('version', 'unknown')}"
        confidence = 0.85
    else:
        # Step 2: Spatial interpolation from reference points
        fnrb, uncertainty, source = spatial_interpolation(lat, lon)
        confidence = 0.70 if "default" in source else 0.75

    # Step 3: Apply CCP cap for cookstove projects
    applied_cap = False
    if fnrb > CCP_FNRB_CAP:
        flags.append(
            f"fNRB {fnrb:.3f} exceeds CCP cookstove cap ({CCP_FNRB_CAP}). "
            f"Capped at {CCP_FNRB_CAP}. Requires MoFuSS justification for higher values."
        )
        fnrb = CCP_FNRB_CAP
        applied_cap = True
        confidence *= 0.90  # Penalty for capping

    # Step 4: Fuel-specific adjustments
    if fuel_type == "charcoal":
        # Charcoal often has higher NRB due to market-driven production
        fnrb *= 1.05
        uncertainty *= 1.10
        flags.append("Charcoal fuel: +5% fNRB adjustment applied")
    elif fuel_type in ("biogas", "lpg", "ethanol"):
        # These are typically 100% fossil or renewable, not biomass
        flags.append(f"Fuel type {fuel_type} is not biomass; fNRB may not apply directly")

    # Step 5: Age-based uncertainty increase for old reference data
    ref_year = assessment_year
    if mofuss_result and "year" in mofuss_result:
        ref_year = mofuss_result["year"]
    elif not mofuss_result:
        # Extract year from source if possible
        for (rlat, rlon), data in DEFAULT_REFERENCE_POINTS.items():
            if haversine_distance(lat, lon, rlat, rlon) < 1.0:
                ref_year = data.get("year", assessment_year)
                break

    year_diff = assessment_year - ref_year
    if year_diff > 5:
        uncertainty += 0.02 * min(year_diff - 5, 10)  # +2% per year after 5 years
        flags.append(f"Reference data is {year_diff} years old; uncertainty increased")

    uncertainty = min(uncertainty, 0.30)  # Max 30% uncertainty
    confidence = max(0.0, min(1.0, confidence))

    # Step 6: Final validation
    if fnrb > CCP_FNRB_CAP and not applied_cap:
        flags.append(
            f"CRITICAL: fNRB {fnrb:.3f} exceeds CCP cap without justification. "
            "Must provide MoFuSS model output or peer-reviewed study."
        )

    return {
        "fnrb_value": round(fnrb, 4),
        "uncertainty_range": {
            "lower": round(max(0.0, fnrb - uncertainty), 4),
            "upper": round(min(1.0, fnrb + uncertainty), 4),
            "std_dev": round(uncertainty, 4),
        },
        "source_reference": source,
        "confidence_score": round(confidence, 4),
        "flags": flags,
        "assessment_year": assessment_year,
        "fuel_type": fuel_type,
        "ccp_cap_applied": applied_cap,
    }
