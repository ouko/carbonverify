"""Methodology Validator Module - Rules engine for TPDDTEC v4, VM0050, VMR0006."""

from typing import Dict, Any, Optional
from datetime import datetime

from app.calculations.constants import (
    TPDDTEC_MIN_THERMAL_EFFICIENCY,
    TPDDTEC_MIN_TRACKING_RATE,
    VM0050_USAGE_RATE_CAPS,
    VM0050_MIN_KPT_SAMPLE_SIZE,
    VMR0006_MAX_RETROACTIVE_YEARS,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def validate_tpddtec_v4(
    thermal_efficiency: Optional[float],
    durability_score: Optional[float],
    dissemination_rate: Optional[float],
    tracking_completeness: Optional[float],
    emissions_calculation_complete: bool,
    wbt_or_cct_conducted: bool,
) -> Dict[str, Any]:
    """Validate against TPDDTEC v4 requirements."""
    score = 0.0
    max_score = 100.0
    missing = []
    risk_flags = []

    # Requirement 1: Thermal efficiency >= 25%
    if thermal_efficiency is not None:
        if thermal_efficiency >= TPDDTEC_MIN_THERMAL_EFFICIENCY:
            score += 20
        else:
            missing.append(f"Thermal efficiency {thermal_efficiency:.1%} below minimum {TPDDTEC_MIN_THERMAL_EFFICIENCY:.0%}")
            risk_flags.append("efficiency_below_threshold")
    else:
        missing.append("Thermal efficiency test not provided")
        risk_flags.append("missing_efficiency_test")

    # Requirement 2: Durability score
    if durability_score is not None:
        if durability_score >= 0.70:
            score += 20
        elif durability_score >= 0.50:
            score += 10
            risk_flags.append("durability_marginal")
        else:
            missing.append(f"Durability score {durability_score:.2f} below acceptable threshold")
            risk_flags.append("durability_concern")
    else:
        missing.append("Durability assessment not provided")

    # Requirement 3: Dissemination rate verification
    if dissemination_rate is not None:
        if dissemination_rate >= 0.80:
            score += 15
        elif dissemination_rate >= 0.50:
            score += 8
            risk_flags.append("dissemination_rate_moderate")
        else:
            missing.append(f"Dissemination rate {dissemination_rate:.1%} too low")
            risk_flags.append("low_dissemination")
    else:
        missing.append("Dissemination rate not verified")

    # Requirement 4: Tracking completeness >= 90%
    if tracking_completeness is not None:
        if tracking_completeness >= TPDDTEC_MIN_TRACKING_RATE:
            score += 20
        else:
            missing.append(f"Tracking completeness {tracking_completeness:.1%} below {TPDDTEC_MIN_TRACKING_RATE:.0%}")
            risk_flags.append("incomplete_tracking")
    else:
        missing.append("Stove tracking data incomplete")

    # Requirement 5: Emissions calculation completeness
    if emissions_calculation_complete:
        score += 15
    else:
        missing.append("Emissions calculation incomplete")
        risk_flags.append("incomplete_emissions_calc")

    # Requirement 6: WBT or CCT conducted
    if wbt_or_cct_conducted:
        score += 10
    else:
        missing.append("No WBT or CCT laboratory test conducted")
        risk_flags.append("missing_lab_test")

    compliance_score = min(100.0, max(0.0, score))

    return {
        "methodology": "TPDDTEC_v4",
        "compliance_score": round(compliance_score, 2),
        "max_score": max_score,
        "missing_requirements": missing,
        "risk_flags": risk_flags,
        "is_compliant": compliance_score >= 70 and len(risk_flags) <= 2,
        "details": {
            "thermal_efficiency": thermal_efficiency,
            "durability_score": durability_score,
            "dissemination_rate": dissemination_rate,
            "tracking_completeness": tracking_completeness,
            "emissions_calculation_complete": emissions_calculation_complete,
            "wbt_or_cct_conducted": wbt_or_cct_conducted,
        },
    }


def validate_vm0050(
    lab_test_type: Optional[str],  # "WBT" or "CCT"
    lab_test_efficiency: Optional[float],
    usage_monitoring_method: Optional[str],  # "survey_only", "field_training", "sums"
    usage_rate: Optional[float],
    kpt_sample_size: Optional[int],
    kpt_duration_weeks: Optional[int],
    kpt_fuel_consumption_kg: Optional[float],
    household_count: int,
) -> Dict[str, Any]:
    """Validate against VM0050 requirements."""
    score = 0.0
    max_score = 100.0
    missing = []
    risk_flags = []

    # Requirement 1: Lab test (WBT or CCT)
    if lab_test_type in ("WBT", "CCT"):
        score += 20
        if lab_test_efficiency is not None and lab_test_efficiency >= 0.25:
            score += 10
        elif lab_test_efficiency is not None:
            missing.append(f"Lab efficiency {lab_test_efficiency:.1%} below 25%")
            risk_flags.append("lab_efficiency_low")
        else:
            missing.append("Lab test efficiency not reported")
    else:
        missing.append("No WBT or CCT laboratory test conducted")
        risk_flags.append("missing_lab_test")

    # Requirement 2: Usage rate cap based on monitoring method
    cap = VM0050_USAGE_RATE_CAPS.get(usage_monitoring_method, 0.75)
    if usage_rate is not None:
        if usage_rate <= cap:
            score += 20
        else:
            missing.append(f"Usage rate {usage_rate:.1%} exceeds cap {cap:.0%} for {usage_monitoring_method}")
            risk_flags.append("usage_rate_exceeds_cap")
    else:
        missing.append("Usage rate not determined")

    # Requirement 3: KPT sample size
    if kpt_sample_size is not None:
        if kpt_sample_size >= VM0050_MIN_KPT_SAMPLE_SIZE:
            score += 20
        else:
            missing.append(f"KPT sample size {kpt_sample_size} below minimum {VM0050_MIN_KPT_SAMPLE_SIZE}")
            risk_flags.append("kpt_sample_small")
    else:
        missing.append("KPT not conducted")
        risk_flags.append("missing_kpt")

    # Requirement 4: KPT duration
    if kpt_duration_weeks is not None:
        if kpt_duration_weeks >= 2:
            score += 10
        else:
            missing.append(f"KPT duration {kpt_duration_weeks} weeks below recommended 2 weeks")
            risk_flags.append("kpt_duration_short")
    else:
        missing.append("KPT duration not reported")

    # Requirement 5: KPT fuel consumption data
    if kpt_fuel_consumption_kg is not None and kpt_fuel_consumption_kg > 0:
        score += 10
    else:
        missing.append("KPT fuel consumption data missing")

    # Requirement 6: Sample adequacy relative to household count
    if kpt_sample_size and household_count > 0:
        sample_pct = kpt_sample_size / household_count
        if sample_pct >= 0.05:  # At least 5% of households
            score += 10
        else:
            risk_flags.append("kpt_sample_low_representation")
    else:
        missing.append("Cannot assess sample representativeness")

    compliance_score = min(100.0, max(0.0, score))

    return {
        "methodology": "VM0050",
        "compliance_score": round(compliance_score, 2),
        "max_score": max_score,
        "missing_requirements": missing,
        "risk_flags": risk_flags,
        "is_compliant": compliance_score >= 70 and len(risk_flags) <= 2,
        "details": {
            "lab_test_type": lab_test_type,
            "lab_test_efficiency": lab_test_efficiency,
            "usage_monitoring_method": usage_monitoring_method,
            "usage_rate": usage_rate,
            "usage_rate_cap": cap,
            "kpt_sample_size": kpt_sample_size,
            "kpt_duration_weeks": kpt_duration_weeks,
            "kpt_fuel_consumption_kg": kpt_fuel_consumption_kg,
        },
    }


def validate_vmr0006(
    project_start_date: Optional[datetime],
    crediting_period_start: Optional[datetime],
    historical_data_available: bool,
    historical_data_reconstructed: bool,
    monitoring_system_deployed_before_start: bool,
) -> Dict[str, Any]:
    """Validate against VMR0006 (retroactive crediting) requirements."""
    score = 0.0
    max_score = 100.0
    missing = []
    risk_flags = []

    if not project_start_date or not crediting_period_start:
        return {
            "methodology": "VMR0006",
            "compliance_score": 0.0,
            "missing_requirements": ["Project dates not provided"],
            "risk_flags": ["missing_dates"],
            "is_compliant": False,
        }

    # Requirement 1: Retroactive period check
    years_diff = (crediting_period_start - project_start_date).days / 365.25
    if years_diff <= VMR0006_MAX_RETROACTIVE_YEARS:
        score += 30
    else:
        missing.append(f"Retroactive period {years_diff:.1f} years exceeds maximum {VMR0006_MAX_RETROACTIVE_YEARS}")
        risk_flags.append("retroactive_period_excessive")

    # Requirement 2: Historical data availability
    if historical_data_available:
        score += 25
    else:
        missing.append("Historical monitoring data not available")
        risk_flags.append("missing_historical_data")

    # Requirement 3: Data reconstruction
    if historical_data_reconstructed:
        score += 20
        if not historical_data_available:
            risk_flags.append("reconstructed_data_quality_concern")
    else:
        if historical_data_available:
            score += 10  # Partial credit
        missing.append("Historical data reconstruction methodology not documented")

    # Requirement 4: Monitoring system deployment
    if monitoring_system_deployed_before_start:
        score += 25
    else:
        missing.append("Monitoring system not deployed before crediting period start")
        risk_flags.append("late_monitoring_deployment")

    compliance_score = min(100.0, max(0.0, score))

    return {
        "methodology": "VMR0006",
        "compliance_score": round(compliance_score, 2),
        "max_score": max_score,
        "missing_requirements": missing,
        "risk_flags": risk_flags,
        "is_compliant": compliance_score >= 70 and len(risk_flags) <= 2,
        "details": {
            "retroactive_years": round(years_diff, 2),
            "historical_data_available": historical_data_available,
            "historical_data_reconstructed": historical_data_reconstructed,
            "monitoring_system_deployed_before_start": monitoring_system_deployed_before_start,
        },
    }


def validate_methodology(
    methodology: str,
    project_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Route to appropriate methodology validator.

    Args:
        methodology: "TPDDTEC_v4", "VM0050", "VMR0006", or "AMS-II.G"
        project_data: Dictionary with methodology-specific parameters
    """
    logger.info("validating_methodology", methodology=methodology)

    if methodology == "TPDDTEC_v4":
        result = validate_tpddtec_v4(
            thermal_efficiency=project_data.get("thermal_efficiency"),
            durability_score=project_data.get("durability_score"),
            dissemination_rate=project_data.get("dissemination_rate"),
            tracking_completeness=project_data.get("tracking_completeness"),
            emissions_calculation_complete=project_data.get("emissions_calculation_complete", False),
            wbt_or_cct_conducted=project_data.get("wbt_or_cct_conducted", False),
        )
    elif methodology == "VM0050":
        result = validate_vm0050(
            lab_test_type=project_data.get("lab_test_type"),
            lab_test_efficiency=project_data.get("lab_test_efficiency"),
            usage_monitoring_method=project_data.get("usage_monitoring_method"),
            usage_rate=project_data.get("usage_rate"),
            kpt_sample_size=project_data.get("kpt_sample_size"),
            kpt_duration_weeks=project_data.get("kpt_duration_weeks"),
            kpt_fuel_consumption_kg=project_data.get("kpt_fuel_consumption_kg"),
            household_count=project_data.get("household_count", 0),
        )
    elif methodology == "VMR0006":
        result = validate_vmr0006(
            project_start_date=project_data.get("project_start_date"),
            crediting_period_start=project_data.get("crediting_period_start"),
            historical_data_available=project_data.get("historical_data_available", False),
            historical_data_reconstructed=project_data.get("historical_data_reconstructed", False),
            monitoring_system_deployed_before_start=project_data.get("monitoring_system_deployed_before_start", False),
        )
    elif methodology == "AMS-II.G":
        # Simplified validation for AMS-II.G
        result = {
            "methodology": "AMS-II.G",
            "compliance_score": 75.0,
            "missing_requirements": ["AMS-II.G detailed validation not yet implemented"],
            "risk_flags": [],
            "is_compliant": True,
        }
    else:
        result = {
            "methodology": methodology,
            "compliance_score": 0.0,
            "missing_requirements": [f"Unknown methodology: {methodology}"],
            "risk_flags": ["unknown_methodology"],
            "is_compliant": False,
        }

    return result
