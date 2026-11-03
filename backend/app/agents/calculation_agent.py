"""CalculationAgent: runs the full carbon calculation pipeline."""

from typing import Any

from sqlalchemy import select

from app.agents.base import BLEND_FORMULA, AgentResult, BaseAgent
from app.calculations.emissions_quantifier import quantify_emissions
from app.calculations.fnrb_calculator import calculate_fnrb
from app.calculations.leakage_detector import assess_leakage
from app.calculations.methodology_validator import validate_methodology
from app.calculations.uncertainty_engine import run_full_uncertainty_analysis
from app.core.logging import get_logger
from app.models import CalculationRun, DataSource, Project

logger = get_logger(__name__)

PLAUSIBILITY_SCHEMA = {
    "type": "object",
    "properties": {
        "plausibility": {
            "type": "number",
            "description": "0-1 score: does the tCO2e magnitude plausibly follow from the activity data?",
        },
        "rationale": {"type": "string"},
    },
    "required": ["plausibility", "rationale"],
}


class CalculationAgent(BaseAgent):
    """Agent that orchestrates the full emissions calculation pipeline."""

    agent_type = "calculation"

    async def run(self, context: dict[str, Any]) -> AgentResult:
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
                reasoning="Calculation aborted: project record not found.",
                evidence={},
            )

        # Data coverage: fraction of project data sources that passed validation.
        ds_result = await self.db.execute(
            select(DataSource).where(DataSource.project_id == project_id)
        )
        data_sources = ds_result.scalars().all()
        if data_sources:
            valid_sources = sum(
                1 for ds in data_sources
                if (ds.validation_status.value if hasattr(ds.validation_status, "value") else str(ds.validation_status)) == "valid"
            )
            data_coverage = valid_sources / len(data_sources)
        else:
            valid_sources = 0
            data_coverage = 0.0

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

        # Calculate agent confidence (heuristic, uncertainty-aware):
        # 30% uncertainty magnitude (lower CI width = higher confidence)
        # 30% methodology compliance
        # 20% fNRB confidence
        # 20% data coverage from validated sources
        uncertainty_width = emissions_result.get("uncertainty_95ci", 0)
        baseline_emissions = emissions_result["baseline_emissions"]["total_tco2e_per_year"]
        uncertainty_ratio = uncertainty_width / baseline_emissions if baseline_emissions > 0 else 0
        uncertainty_confidence = max(0, 1.0 - (uncertainty_ratio * 2))

        methodology_confidence = methodology_result["compliance_score"] / 100.0
        fnrb_confidence = fnrb_result.get("confidence_score", 0.8)

        heuristic = (
            uncertainty_confidence * 0.30
            + methodology_confidence * 0.30
            + fnrb_confidence * 0.20
            + data_coverage * 0.20
        )
        heuristic = max(0.0, min(1.0, heuristic))

        # LLM sanity check: does the tCO2e magnitude follow from the inputs?
        gross_reductions = emissions_result["net_reductions"]["gross_reduction_tco2e"]
        llm_review = await self.reason_with_llm(
            task_prompt=(
                "Sanity-check this emissions calculation. Given the activity data "
                "(households, fuel consumption, efficiencies), does the resulting "
                "tCO2e magnitude plausibly follow? Score plausibility 0-1."
            ),
            context={
                "household_count": household_count,
                "fuel_consumption_kg_per_day": fuel_consumption,
                "thermal_efficiency": thermal_efficiency,
                "baseline_efficiency": baseline_efficiency,
                "fnrb": fnrb_result["fnrb_value"],
                "baseline_emissions_tco2e_per_year": baseline_emissions,
                "gross_reduction_tco2e": gross_reductions,
                "net_reduction_tco2e": emissions_result["net_reductions"]["net_reduction_tco2e"],
                "uncertainty_95ci": uncertainty_width,
                "methodology_compliance_pct": methodology_result["compliance_score"],
                "data_coverage": data_coverage,
            },
            response_schema=PLAUSIBILITY_SCHEMA,
        )
        llm_plausibility: float | None = None
        llm_rationale = ""
        if not llm_review.get("_fallback"):
            raw = llm_review.get("plausibility")
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                llm_plausibility = max(0.0, min(1.0, float(raw)))
            llm_rationale = str(llm_review.get("rationale", ""))

        confidence = self.blend_confidence(heuristic, llm_plausibility)
        blend_note = (
            f"Blended heuristic ({heuristic:.2f}) with LLM plausibility ({llm_plausibility:.2f}) "
            f"via {BLEND_FORMULA}."
            if llm_plausibility is not None
            else f"LLM sanity check unavailable; heuristic score stands alone (blending {BLEND_FORMULA} not applied)."
        )

        reasoning = (
            f"Ran engines for {household_count} households, {fuel_consumption} kg/day fuel: "
            f"fNRB {fnrb_result['fnrb_value']:.3f} (confidence {fnrb_confidence:.2f}); "
            f"baseline {baseline_emissions:.1f} tCO2e/yr, gross reductions {gross_reductions:.1f} tCO2e/yr, "
            f"leakage {leakage_result['total_leakage_tco2e']:.1f} tCO2e; "
            f"uncertainty 95CI ±{uncertainty_width:.1f} ({uncertainty_ratio:.1%} of baseline); "
            f"methodology compliance {methodology_result['compliance_score']:.0f}%; "
            f"data coverage {data_coverage:.0%} ({valid_sources}/{len(data_sources)} sources valid). "
            f"{blend_note}"
            + (f" LLM rationale: {llm_rationale}" if llm_rationale else "")
        )

        evidence = {
            "fnrb_value": fnrb_result["fnrb_value"],
            "fnrb_confidence": fnrb_confidence,
            "baseline_emissions_tco2e_per_year": baseline_emissions,
            "gross_reduction_tco2e": gross_reductions,
            "leakage_tco2e": leakage_result["total_leakage_tco2e"],
            "uncertainty_95ci": uncertainty_width,
            "uncertainty_ratio": round(uncertainty_ratio, 4),
            "methodology_compliance_pct": methodology_result["compliance_score"],
            "data_coverage": round(data_coverage, 3),
            "valid_sources": valid_sources,
            "total_sources": len(data_sources),
            "conservative_issuance_tco2e": uncertainty_result.get("conservative_issuance_tco2e"),
            "llm_plausibility": llm_plausibility,
        }

        output = self.build_output(
            reasoning,
            evidence,
            calculation_run_id=str(calc_run.id),
            fnrb=fnrb_result,
            emissions=emissions_result,
            leakage=leakage_result,
            methodology_validation=methodology_result,
            uncertainty=uncertainty_result,
            heuristic_confidence=round(heuristic, 3),
            llm_plausibility=llm_plausibility,
        )

        status = "completed" if confidence >= 0.85 else "queued_for_review"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
            reasoning=reasoning,
            evidence=evidence,
        )
