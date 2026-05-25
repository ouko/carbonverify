"""Uncertainty Engine - Monte Carlo simulation and sensitivity analysis."""

from typing import Dict, Any, List, Optional, Callable

from app.calculations.emissions_quantifier import run_monte_carlo
from app.core.logging import get_logger

logger = get_logger(__name__)


def tornado_sensitivity_analysis(
    base_params: Dict[str, float],
    param_ranges: Dict[str, tuple],  # {name: (low, high)}
    output_func: Callable[[Dict[str, float]], float],
) -> List[Dict[str, Any]]:
    """
    Perform tornado sensitivity analysis.

    Varies each parameter ±10% from base while holding others constant,
    measuring impact on output.
    """
    base_output = output_func(base_params)
    sensitivities = []

    for param_name, (low, high) in param_ranges.items():
        # Low variation
        low_params = dict(base_params)
        low_params[param_name] = low
        low_output = output_func(low_params)

        # High variation
        high_params = dict(base_params)
        high_params[param_name] = high
        high_output = output_func(high_params)

        # Calculate swing
        swing = abs(high_output - low_output)
        swing_pct = (swing / abs(base_output) * 100) if base_output != 0 else 0

        sensitivities.append({
            "parameter": param_name,
            "base_value": base_params.get(param_name),
            "low_value": low,
            "high_value": high,
            "low_output": round(low_output, 4),
            "high_output": round(high_output, 4),
            "swing": round(swing, 4),
            "swing_percentage": round(swing_pct, 2),
        })

    # Sort by swing magnitude (descending)
    sensitivities.sort(key=lambda x: x["swing"], reverse=True)

    return sensitivities


def run_sensitivity_analysis(
    fuel_consumption_kg_per_day: float,
    fuel_type: str,
    household_count: int,
    thermal_efficiency: float,
    baseline_efficiency: float,
    fnrb: float,
    fnrb_uncertainty: float = 0.10,
) -> List[Dict[str, Any]]:
    """
    Run tornado sensitivity analysis on key emission parameters.
    """
    from app.calculations.emissions_quantifier import calculate_net_reductions
    from app.calculations.emissions_quantifier import calculate_baseline_emissions
    from app.calculations.emissions_quantifier import calculate_project_emissions

    def output_fn(params: Dict[str, float]) -> float:
        baseline = calculate_baseline_emissions(
            fuel_consumption_kg_per_day=params["fuel_consumption"],
            fuel_type=params["fuel_type"],
            household_count=int(params["household_count"]),
            fnrb=params["fnrb"],
        )
        project = calculate_project_emissions(
            fuel_consumption_kg_per_day=params["fuel_consumption"],
            fuel_type=params["fuel_type"],
            household_count=int(params["household_count"]),
            thermal_efficiency=params["thermal_efficiency"],
            baseline_efficiency=params["baseline_efficiency"],
            fnrb=params["fnrb"],
        )
        net = calculate_net_reductions(baseline, project)
        return net["net_reduction_tco2e"]

    base_params = {
        "fuel_consumption": fuel_consumption_kg_per_day,
        "fuel_type": 0,  # Not varied in tornado
        "household_count": float(household_count),
        "thermal_efficiency": thermal_efficiency,
        "baseline_efficiency": baseline_efficiency,
        "fnrb": fnrb,
    }

    param_ranges = {
        "fuel_consumption": (
            fuel_consumption_kg_per_day * 0.80,
            fuel_consumption_kg_per_day * 1.20,
        ),
        "thermal_efficiency": (
            max(0.05, thermal_efficiency * 0.85),
            min(0.95, thermal_efficiency * 1.15),
        ),
        "baseline_efficiency": (
            max(0.05, baseline_efficiency * 0.85),
            min(0.20, baseline_efficiency * 1.15),
        ),
        "fnrb": (
            max(0.0, fnrb - fnrb_uncertainty),
            min(0.50, fnrb + fnrb_uncertainty),
        ),
        "household_count": (
            max(1, household_count * 0.90),
            household_count * 1.10,
        ),
    }

    return tornado_sensitivity_analysis(base_params, param_ranges, output_fn)


def run_full_uncertainty_analysis(
    fuel_consumption_kg_per_day: float,
    fuel_type: str,
    household_count: int,
    thermal_efficiency: float,
    baseline_efficiency: float,
    fnrb: float,
    fnrb_uncertainty: float = 0.10,
    leakage_assessment: Optional[Dict[str, Any]] = None,
    n_iterations: int = 10_000,
) -> Dict[str, Any]:
    """
    Run complete uncertainty analysis: Monte Carlo + sensitivity.
    """
    logger.info("running_uncertainty_analysis", households=household_count, iterations=n_iterations)

    # Monte Carlo
    mc_result = run_monte_carlo(
        fuel_consumption_kg_per_day=fuel_consumption_kg_per_day,
        fuel_type=fuel_type,
        household_count=household_count,
        thermal_efficiency=thermal_efficiency,
        baseline_efficiency=baseline_efficiency,
        fnrb=fnrb,
        fnrb_uncertainty=fnrb_uncertainty,
        n_iterations=n_iterations,
    )

    # Sensitivity
    sensitivity = run_sensitivity_analysis(
        fuel_consumption_kg_per_day=fuel_consumption_kg_per_day,
        fuel_type=fuel_type,
        household_count=household_count,
        thermal_efficiency=thermal_efficiency,
        baseline_efficiency=baseline_efficiency,
        fnrb=fnrb,
        fnrb_uncertainty=fnrb_uncertainty,
    )

    # Conservative crediting recommendation
    conservative = mc_result["conservative_estimate_tco2e"]

    return {
        "monte_carlo": mc_result,
        "sensitivity_analysis": sensitivity,
        "conservative_issuance_tco2e": round(conservative, 4),
        "recommendation": (
            f"Recommend issuance at lower 95% CI: {conservative:.2f} tCO2e/year"
            f" (mean: {mc_result['mean_reduction_tco2e']:.2f})"
        ),
    }
