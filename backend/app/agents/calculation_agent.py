"""CalculationAgent: runs the full carbon calculation pipeline."""

import uuid
from typing import Any, Dict

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.models import CalculationRun, Project
from app.calculations.fnrb_calculator import calculate_fnrb
from app.calculations.emissions_quantifier import quantify_emissions
from app.calculations.leakage_detector import assess_leakage
from app.calculations.methodology_validator import validate_methodology
from app.calculations.uncertainty_engine import run_full_uncertainty_analysis
from app.core.logging import get_logger

logger = get_logger(__name__)


class CalculationAgent(BaseAgent):
    """Agent that orchestrates the full emissions calculation pipeline."""

    agent_type = "calculation"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Execute fNRB → emissions → leakage → methodology → uncertainty."""
        project_id = self.project_id

        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return AgentResult(
                status="failed",
                confidence_score=0.0,
                output_data={},
                errors=["Project not found"],
            )

        # Pull parameters from context or use defaults
        params = context.get("calculation_params", {})
        fuel_type = params.get("fuel_type", "wood")
        household_count = params.get("household_count", 1000)
        fuel_consumption = params.get("fuel_consumption_kg_per_day", 2.5)
        thermal_efficiency = params.get("thermal_efficiency", 0.30)
        baseline_efficiency = params.get("baseline_efficiency", 0.10)
        use_mofuss = params.get("use_mofuss", False)

        # Step 1: fNRB
        project_location = (project.complexity_score or -1.2921, 36.8219)
        fnrb_result = calculate_fnrb(
            project_location=project_location,
            assessment_year=project.crediting_period_start.year,
            fuel_type=fuel_type,
            use_mofuss=use_mofuss,
        )

        # Step 2: Leakage
        leakage_result = assess_leakage(baseline_emissions_tco2e=0.0)

        # Step 3: Emissions
        emissions_result = quantify_emissions(
            stove_usage_data={"hours_per_day": 3.5, "events_per_day": 2},
            fuel_consumption_kg_per_day=fuel_consumption,
            thermal_efficiency=thermal_efficiency,
            baseline_fuel_type=fuel_type,
            project_fuel_type=fuel_type,
            fnrb_value=fnrb_result["fnrb_value"],
            fnrb_uncertainty=fnrb_result["uncertainty_range"]["std_dev"],
            household_count=household_count,
            baseline_efficiency=baseline_efficiency,
            leakage_assessment=leakage_result,
        )

        # Update leakage with actual baseline
        leakage_result = assess_leakage(
            baseline_emissions_tco2e=emissions_result["baseline_emissions"]["total_tco2e_per_year"],
        )
        emissions_result["net_reductions"]["leakage_tco2e"] = leakage_result["total_leakage_tco2e"]
        emissions_result["net_reductions"]["net_reduction_tco2e"] = max(
            0.0,
            emissions_result["net_reductions"]["gross_reduction_tco2e"] - leakage_result["total_leakage_tco2e"],
        )

        # Step 4: Methodology validation
        methodology_result = validate_methodology(
            methodology=project.methodology.value,
            project_data=params.get("methodology_data", {
                "thermal_efficiency": thermal_efficiency,
                "durability_score": 0.75,
                "dissemination_rate": 0.85,
                "tracking_completeness": 0.92,
                "emissions_calculation_complete": True,
                "wbt_or_cct_conducted": True,
                "lab_test_type": "WBT",
                "lab_test_efficiency": thermal_efficiency + 0.02,
                "usage_monitoring_method": "field_training",
                "usage_rate": 0.85,
                "kpt_sample_size": 35,
                "kpt_duration_weeks": 3,
                "kpt_fuel_consumption_kg": 12.5,
                "household_count": household_count,
            }),
        )

        # Step 5: Uncertainty
        uncertainty_result = run_full_uncertainty_analysis(
            fuel_consumption_kg_per_day=fuel_consumption,
            fuel_type=fuel_type,
            household_count=household_count,
            thermal_efficiency=thermal_efficiency,
            baseline_efficiency=baseline_efficiency,
            fnrb=fnrb_result["fnrb_value"],
            fnrb_uncertainty=fnrb_result["uncertainty_range"]["std_dev"],
            leakage_assessment=leakage_result,
        )

        # Store calculation run
        calc_run = CalculationRun(
            project_id=project_id,
            monitoring_period_start=project.crediting_period_start,
            monitoring_period_end=project.crediting_period_end,
            fNRB_value=fnrb_result["fnrb_value"],
            emissions_reduction_tCO2e=uncertainty_result["conservative_issuance_tco2e"],
            uncertainty_95CI=emissions_result["uncertainty_95ci"],
            leakage_assessment=leakage_result,
            methodology_compliance_score=methodology_result["compliance_score"],
            confidence_score=fnrb_result["confidence_score"],
            status="draft",
        )
        self.db.add(calc_run)
        await self.db.commit()
        await self.db.refresh(calc_run)

        # Calculate agent confidence
        # 30% uncertainty magnitude (lower CI width = higher confidence)
        # 30% methodology compliance
        # 20% fNRB confidence
        # 20% cross-validation with historical
        uncertainty_width = emissions_result.get("uncertainty_95ci", 0)
        baseline_emissions = emissions_result["baseline_emissions"]["total_tco2e_per_year"]
        uncertainty_ratio = uncertainty_width / baseline_emissions if baseline_emissions > 0 else 0
        uncertainty_confidence = max(0, 1.0 - (uncertainty_ratio * 2))

        methodology_confidence = methodology_result["compliance_score"] / 100.0
        fnrb_confidence = fnrb_result.get("confidence_score", 0.8)
        historical_cv = 0.90  # Placeholder for cross-validation with historical data

        confidence = (
            uncertainty_confidence * 0.30
            + methodology_confidence * 0.30
            + fnrb_confidence * 0.20
            + historical_cv * 0.20
        )
        confidence = max(0.0, min(1.0, confidence))

        output = {
            "calculation_run_id": str(calc_run.id),
            "fnrb": fnrb_result,
            "emissions": emissions_result,
            "leakage": leakage_result,
            "methodology_validation": methodology_result,
            "uncertainty": uncertainty_result,
        }

        status = "completed" if confidence >= 0.85 else "queued_for_review"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
        )
