"""Emissions Quantifier Module - Baseline, Project, and Net Reduction Calculations."""

import numpy as np
from typing import Dict, Any, Optional, Tuple

from app.calculations.constants import EMISSION_FACTORS, GWP_100
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_emission_factor(fuel_type: str) -> Dict[str, float]:
    """Get emission factor for a fuel type."""
    ef = EMISSION_FACTORS.get(fuel_type, EMISSION_FACTORS["wood"])
    return ef


def calculate_baseline_emissions(
    fuel_consumption_kg_per_day: float,
    fuel_type: str,
    household_count: int,
    cooking_days_per_year: float = 350.0,
    fnrb: float = 1.0,
) -> Dict[str, Any]:
    """
    Calculate baseline emissions using IPCC Tier 1/2 methodology.

    Baseline emissions = fuel_consumed × NCV × EF_CO2 × fNRB
    Plus non-CO2 (CH4, N2O) emissions
    """
    ef = get_emission_factor(fuel_type)

    annual_fuel_kg = fuel_consumption_kg_per_day * cooking_days_per_year * household_count

    # CO2 from non-renewable biomass
    ncv_gj = ef["ncv_mj_per_kg"] / 1000.0  # MJ/kg -> GJ/kg
    co2_tonnes = annual_fuel_kg * ncv_gj * ef["co2ef_kg_per_gj"] / 1000.0 * fnrb

    # Non-CO2 emissions (always counted as they are non-renewable regardless of biomass origin)
    ch4_tonnes = annual_fuel_kg * ef["ch4ef_g_per_kg"] / 1_000_000.0 * GWP_100["ch4_bio"]
    n2o_tonnes = annual_fuel_kg * ef["n2oef_g_per_kg"] / 1_000_000.0 * GWP_100["n2o"]

    total_tco2e = co2_tonnes + ch4_tonnes + n2o_tonnes

    return {
        "annual_fuel_kg": round(annual_fuel_kg, 2),
        "co2_tonnes": round(co2_tonnes, 4),
        "ch4_tco2e": round(ch4_tonnes, 4),
        "n2o_tco2e": round(n2o_tonnes, 4),
        "total_tco2e_per_year": round(total_tco2e, 4),
        "fuel_type": fuel_type,
        "fnrb_applied": fnrb,
    }


def calculate_project_emissions(
    fuel_consumption_kg_per_day: float,
    fuel_type: str,
    household_count: int,
    thermal_efficiency: float,
    baseline_efficiency: float,
    cooking_days_per_year: float = 350.0,
    fnrb: float = 1.0,
) -> Dict[str, Any]:
    """
    Calculate project emissions accounting for efficiency improvement.

    Project fuel = Baseline fuel × (baseline_efficiency / project_efficiency)
    Project emissions = Project fuel × EF × fNRB
    """
    ef = get_emission_factor(fuel_type)

    # Adjust fuel consumption for efficiency
    efficiency_ratio = baseline_efficiency / max(thermal_efficiency, 0.01)
    project_fuel_kg_per_day = fuel_consumption_kg_per_day * efficiency_ratio

    annual_fuel_kg = project_fuel_kg_per_day * cooking_days_per_year * household_count

    ncv_gj = ef["ncv_mj_per_kg"] / 1000.0
    co2_tonnes = annual_fuel_kg * ncv_gj * ef["co2ef_kg_per_gj"] / 1000.0 * fnrb

    ch4_tonnes = annual_fuel_kg * ef["ch4ef_g_per_kg"] / 1_000_000.0 * GWP_100["ch4_bio"]
    n2o_tonnes = annual_fuel_kg * ef["n2oef_g_per_kg"] / 1_000_000.0 * GWP_100["n2o"]

    total_tco2e = co2_tonnes + ch4_tonnes + n2o_tonnes

    return {
        "annual_fuel_kg": round(annual_fuel_kg, 2),
        "efficiency_ratio": round(efficiency_ratio, 4),
        "project_thermal_efficiency": round(thermal_efficiency, 4),
        "baseline_thermal_efficiency": round(baseline_efficiency, 4),
        "co2_tonnes": round(co2_tonnes, 4),
        "ch4_tco2e": round(ch4_tonnes, 4),
        "n2o_tco2e": round(n2o_tonnes, 4),
        "total_tco2e_per_year": round(total_tco2e, 4),
    }


def calculate_net_reductions(
    baseline_emissions: Dict[str, Any],
    project_emissions: Dict[str, Any],
    leakage_tco2e: float = 0.0,
) -> Dict[str, Any]:
    """Calculate net emission reductions."""
    baseline_total = baseline_emissions["total_tco2e_per_year"]
    project_total = project_emissions["total_tco2e_per_year"]

    gross_reduction = baseline_total - project_total
    net_reduction = gross_reduction - leakage_tco2e

    return {
        "baseline_emissions_tco2e": round(baseline_total, 4),
        "project_emissions_tco2e": round(project_total, 4),
        "gross_reduction_tco2e": round(gross_reduction, 4),
        "leakage_tco2e": round(leakage_tco2e, 4),
        "net_reduction_tco2e": round(max(0.0, net_reduction), 4),
        "reduction_percentage": round((gross_reduction / baseline_total * 100) if baseline_total > 0 else 0, 2),
    }


def run_monte_carlo(
    fuel_consumption_kg_per_day: float,
    fuel_type: str,
    household_count: int,
    thermal_efficiency: float,
    baseline_efficiency: float,
    fnrb: float,
    fnrb_uncertainty: float,
    fuel_consumption_cv: float = 0.20,  # 20% CV typical for survey data
    efficiency_cv: float = 0.15,         # 15% CV for lab-tested efficiency
    leakage_fraction_mean: float = 0.05,
    leakage_fraction_std: float = 0.03,
    cooking_days_per_year: float = 350.0,
    n_iterations: int = 10_000,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Run Monte Carlo simulation for uncertainty propagation.

    Samples key parameters from distributions and computes emission reductions.
    Returns 95% CI and full distribution statistics.
    """
    rng = np.random.default_rng(random_seed)

    # Sample parameters
    fuel_samples = rng.lognormal(
        mean=np.log(fuel_consumption_kg_per_day),
        sigma=np.sqrt(np.log(1 + fuel_consumption_cv ** 2)),
        size=n_iterations,
    )

    fnrb_samples = rng.beta(
        a=max(0.1, fnrb * ((fnrb * (1 - fnrb)) / (fnrb_uncertainty ** 2) - 1)),
        b=max(0.1, (1 - fnrb) * ((fnrb * (1 - fnrb)) / (fnrb_uncertainty ** 2) - 1)),
        size=n_iterations,
    )
    fnrb_samples = np.clip(fnrb_samples, 0.0, 1.0)

    efficiency_samples = rng.lognormal(
        mean=np.log(thermal_efficiency),
        sigma=np.sqrt(np.log(1 + efficiency_cv ** 2)),
        size=n_iterations,
    )
    efficiency_samples = np.clip(efficiency_samples, 0.01, 0.99)

    leakage_fraction_samples = rng.beta(
        a=max(0.5, leakage_fraction_mean * 10),
        b=max(0.5, (1 - leakage_fraction_mean) * 10),
        size=n_iterations,
    )
    leakage_fraction_samples = np.clip(leakage_fraction_samples, 0.0, 0.30)

    # Compute emissions for each sample
    ef = get_emission_factor(fuel_type)
    ncv_gj = ef["ncv_mj_per_kg"] / 1000.0

    annual_fuel_baseline = fuel_samples * cooking_days_per_year * household_count
    co2_baseline = annual_fuel_baseline * ncv_gj * ef["co2ef_kg_per_gj"] / 1000.0 * fnrb_samples
    ch4_baseline = annual_fuel_baseline * ef["ch4ef_g_per_kg"] / 1_000_000.0 * GWP_100["ch4_bio"]
    n2o_baseline = annual_fuel_baseline * ef["n2oef_g_per_kg"] / 1_000_000.0 * GWP_100["n2o"]
    baseline_total = co2_baseline + ch4_baseline + n2o_baseline

    efficiency_ratio = baseline_efficiency / efficiency_samples
    project_fuel = annual_fuel_baseline * efficiency_ratio
    co2_project = project_fuel * ncv_gj * ef["co2ef_kg_per_gj"] / 1000.0 * fnrb_samples
    ch4_project = project_fuel * ef["ch4ef_g_per_kg"] / 1_000_000.0 * GWP_100["ch4_bio"]
    n2o_project = project_fuel * ef["n2oef_g_per_kg"] / 1_000_000.0 * GWP_100["n2o"]
    project_total = co2_project + ch4_project + n2o_project

    gross_reduction = baseline_total - project_total
    leakage = gross_reduction * leakage_fraction_samples
    net_reduction = gross_reduction - leakage
    net_reduction = np.clip(net_reduction, 0.0, None)

    # Statistics
    mean_reduction = float(np.mean(net_reduction))
    std_reduction = float(np.std(net_reduction))
    ci_lower = float(np.percentile(net_reduction, 2.5))
    ci_upper = float(np.percentile(net_reduction, 97.5))
    median = float(np.median(net_reduction))

    return {
        "mean_reduction_tco2e": round(mean_reduction, 4),
        "median_reduction_tco2e": round(median, 4),
        "std_dev": round(std_reduction, 4),
        "uncertainty_95ci": {
            "lower": round(ci_lower, 4),
            "upper": round(ci_upper, 4),
            "width": round(ci_upper - ci_lower, 4),
        },
        "conservative_estimate_tco2e": round(ci_lower, 4),
        "n_iterations": n_iterations,
        "parameter_distributions": {
            "fuel_consumption_cv": fuel_consumption_cv,
            "efficiency_cv": efficiency_cv,
            "fnrb_std": fnrb_uncertainty,
        },
    }


def quantify_emissions(
    stove_usage_data: Dict[str, Any],
    fuel_consumption_kg_per_day: float,
    thermal_efficiency: float,
    baseline_fuel_type: str,
    project_fuel_type: str,
    fnrb_value: float,
    fnrb_uncertainty: float = 0.10,
    household_count: int = 1,
    baseline_efficiency: float = 0.10,
    leakage_assessment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main entry point for emissions quantification.

    Returns comprehensive emissions calculation with Monte Carlo uncertainty.
    """
    logger.info(
        "quantifying_emissions",
        households=household_count,
        fuel_type=project_fuel_type,
        fnrb=fnrb_value,
    )

    # Baseline emissions
    baseline = calculate_baseline_emissions(
        fuel_consumption_kg_per_day=fuel_consumption_kg_per_day,
        fuel_type=baseline_fuel_type,
        household_count=household_count,
        fnrb=fnrb_value,
    )

    # Project emissions
    project = calculate_project_emissions(
        fuel_consumption_kg_per_day=fuel_consumption_kg_per_day,
        fuel_type=project_fuel_type,
        household_count=household_count,
        thermal_efficiency=thermal_efficiency,
        baseline_efficiency=baseline_efficiency,
        fnrb=fnrb_value,
    )

    # Leakage
    leakage_tco2e = 0.0
    if leakage_assessment:
        leakage_tco2e = leakage_assessment.get("total_leakage_tco2e", 0.0)

    # Net reductions (deterministic)
    net = calculate_net_reductions(baseline, project, leakage_tco2e)

    # Monte Carlo uncertainty
    mc = run_monte_carlo(
        fuel_consumption_kg_per_day=fuel_consumption_kg_per_day,
        fuel_type=project_fuel_type,
        household_count=household_count,
        thermal_efficiency=thermal_efficiency,
        baseline_efficiency=baseline_efficiency,
        fnrb=fnrb_value,
        fnrb_uncertainty=fnrb_uncertainty,
        leakage_fraction_mean=leakage_tco2e / net["gross_reduction_tco2e"] if net["gross_reduction_tco2e"] > 0 else 0.05,
    )

    return {
        "baseline_emissions": baseline,
        "project_emissions": project,
        "net_reductions": net,
        "monte_carlo": mc,
        "emissions_reduction_tco2e": mc["mean_reduction_tco2e"],
        "uncertainty_95ci": mc["uncertainty_95ci"]["upper"] - mc["uncertainty_95ci"]["lower"],
        "conservative_issuance_tco2e": mc["conservative_estimate_tco2e"],
    }
