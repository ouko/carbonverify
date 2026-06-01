from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Any, Dict
import uuid

from app.database import get_db
from app.models import (
    CalculationRun,
    Project,
    User,
    AuditActionEnum,
    DataSource,
    ValidationStatusEnum,
    CalculationStatusEnum,
)
from app.schemas import CalculationRunCreate, CalculationRunUpdate, CalculationRunOut
from app.security.audit_logging import AuditLogger
from app.auth.dependencies import require_operator, require_viewer
from app.security.project_auth import require_project_access
from app.api.projects import validate_status_transition
from app.calculations.fnrb_calculator import calculate_fnrb
from app.calculations.emissions_quantifier import quantify_emissions
from app.calculations.leakage_detector import assess_leakage
from app.calculations.methodology_validator import validate_methodology
from app.calculations.uncertainty_engine import run_full_uncertainty_analysis
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/calculations", tags=["calculations"])


VALID_CALCULATION_TRANSITIONS = {
    CalculationStatusEnum.draft: {
        CalculationStatusEnum.review_pending,
        CalculationStatusEnum.approved,
        CalculationStatusEnum.rejected,
    },
    CalculationStatusEnum.review_pending: {
        CalculationStatusEnum.approved,
        CalculationStatusEnum.rejected,
    },
}


def _extract_calc_params(data_sources: List[DataSource]) -> Dict[str, Any]:
    """Merge parameters from validated data sources."""
    merged: Dict[str, Any] = {}
    for ds in data_sources:
        if ds.processed_data:
            merged.update(ds.processed_data)
        if ds.raw_data:
            merged.update(ds.raw_data)
    return merged


@router.get("/", response_model=List[CalculationRunOut])
async def list_calculations(
    project_id: uuid.UUID = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    if project_id:
        await require_project_access(project_id, current_user, db)
    stmt = select(CalculationRun)
    if project_id:
        stmt = stmt.where(CalculationRun.project_id == project_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=CalculationRunOut, status_code=status.HTTP_201_CREATED)
async def create_calculation(
    payload: CalculationRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    await require_project_access(payload.project_id, current_user, db)
    calc = CalculationRun(**payload.model_dump())
    db.add(calc)
    await db.commit()
    await db.refresh(calc)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.calculation_run,
        actor_id=current_user.id,
        target_type="calculation_run",
        target_id=calc.id,
    )
    return calc


@router.get("/{calc_id}", response_model=CalculationRunOut)
async def get_calculation(
    calc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    result = await db.execute(select(CalculationRun).where(CalculationRun.id == calc_id))
    calc = result.scalar_one_or_none()
    if not calc:
        raise HTTPException(status_code=404, detail="Calculation run not found")
    await require_project_access(calc.project_id, current_user, db)
    return calc


@router.patch("/{calc_id}", response_model=CalculationRunOut)
async def update_calculation(
    calc_id: uuid.UUID,
    payload: CalculationRunUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    result = await db.execute(select(CalculationRun).where(CalculationRun.id == calc_id))
    calc = result.scalar_one_or_none()
    if not calc:
        raise HTTPException(status_code=404, detail="Calculation run not found")
    await require_project_access(calc.project_id, current_user, db)
    update_data = payload.model_dump(exclude_unset=True)
    if "status" in update_data:
        new_status = CalculationStatusEnum(update_data["status"])
        validate_status_transition(calc.status, new_status, VALID_CALCULATION_TRANSITIONS)
    for field, value in update_data.items():
        setattr(calc, field, value)
    await db.commit()
    await db.refresh(calc)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="calculation_run",
        target_id=calc.id,
    )
    return calc


@router.delete("/{calc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calculation(
    calc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    result = await db.execute(select(CalculationRun).where(CalculationRun.id == calc_id))
    calc = result.scalar_one_or_none()
    if not calc:
        raise HTTPException(status_code=404, detail="Calculation run not found")
    await require_project_access(calc.project_id, current_user, db)
    await db.delete(calc)
    await db.commit()
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="calculation_run",
        target_id=calc.id,
        metadata={"event": "calculation_deleted"},
    )
    return None


@router.post("/projects/{project_id}/calculate")
async def run_project_calculation(
    project_id: uuid.UUID,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Run full carbon calculation for a project.

    Executes: fNRB -> Emissions -> Leakage -> Methodology Validation -> Uncertainty Analysis
    """
    logger.info("starting_calculation", project_id=str(project_id), methodology=project.methodology.value)

    # Validate data sources
    result = await db.execute(
        select(DataSource).where(
            DataSource.project_id == project_id,
            DataSource.validation_status == ValidationStatusEnum.valid,
        )
    )
    validated_sources = result.scalars().all()
    if not validated_sources:
        raise HTTPException(status_code=400, detail="No validated data sources for this project")

    params = _extract_calc_params(validated_sources)

    # Resolve location
    project_location = params.get("project_location") or params.get("gps") or params.get("coordinates")
    if project_location:
        if isinstance(project_location, dict):
            project_location = (project_location.get("latitude"), project_location.get("longitude"))
        elif isinstance(project_location, (list, tuple)) and len(project_location) == 2:
            project_location = tuple(project_location)
        else:
            project_location = None
    if not project_location or None in project_location:
        raise HTTPException(status_code=400, detail="Project location not available in validated data sources")

    fuel_type = params.get("fuel_type", "wood")
    assessment_year = params.get("assessment_year", project.crediting_period_start.year if project.crediting_period_start else 2024)

    # ─── Step 1: fNRB Calculation ─────────────────────────────────────────────
    fnrb_result = calculate_fnrb(
        project_location=project_location,
        assessment_year=assessment_year,
        fuel_type=fuel_type,
        use_mofuss=False,
    )

    # ─── Step 2: Leakage Assessment ───────────────────────────────────────────
    leakage_result = assess_leakage(
        baseline_emissions_tco2e=0.0,
    )

    # ─── Step 3: Emissions Quantification ─────────────────────────────────────
    emissions_result = quantify_emissions(
        stove_usage_data=params.get("stove_usage_data", {"hours_per_day": 3.5, "events_per_day": 2}),
        fuel_consumption_kg_per_day=params.get("fuel_consumption_kg_per_day", 2.5),
        thermal_efficiency=params.get("thermal_efficiency", 0.30),
        baseline_fuel_type=params.get("baseline_fuel_type", fuel_type),
        project_fuel_type=params.get("project_fuel_type", fuel_type),
        fnrb_value=fnrb_result["fnrb_value"],
        fnrb_uncertainty=fnrb_result["uncertainty_range"]["std_dev"],
        household_count=params.get("household_count", 1000),
        baseline_efficiency=params.get("baseline_efficiency", 0.10),
        leakage_assessment=leakage_result,
    )

    # Update leakage with actual baseline
    leakage_result = assess_leakage(
        baseline_emissions_tco2e=emissions_result["baseline_emissions"]["total_tco2e_per_year"],
    )
    emissions_result["net_reductions"]["leakage_tco2e"] = leakage_result["total_leakage_tco2e"]
    emissions_result["net_reductions"]["net_reduction_tco2e"] = max(
        0.0,
        emissions_result["net_reductions"]["gross_reduction_tco2e"] - leakage_result["total_leakage_tco2e"]
    )

    # ─── Step 4: Methodology Validation ───────────────────────────────────────
    methodology_project_data = {
        "thermal_efficiency": params.get("thermal_efficiency", 0.30),
        "durability_score": params.get("durability_score", 0.75),
        "dissemination_rate": params.get("dissemination_rate", 0.85),
        "tracking_completeness": params.get("tracking_completeness", 0.92),
        "emissions_calculation_complete": params.get("emissions_calculation_complete", True),
        "wbt_or_cct_conducted": params.get("wbt_or_cct_conducted", True),
        "lab_test_type": params.get("lab_test_type", "WBT"),
        "lab_test_efficiency": params.get("lab_test_efficiency", 0.32),
        "usage_monitoring_method": params.get("usage_monitoring_method", "field_training"),
        "usage_rate": params.get("usage_rate", 0.85),
        "kpt_sample_size": params.get("kpt_sample_size", 35),
        "kpt_duration_weeks": params.get("kpt_duration_weeks", 3),
        "kpt_fuel_consumption_kg": params.get("kpt_fuel_consumption_kg", 12.5),
        "household_count": params.get("household_count", 1000),
    }
    methodology_result = validate_methodology(
        methodology=project.methodology.value,
        project_data=methodology_project_data,
    )

    # ─── Step 5: Uncertainty Analysis ─────────────────────────────────────────
    uncertainty_result = run_full_uncertainty_analysis(
        fuel_consumption_kg_per_day=params.get("fuel_consumption_kg_per_day", 2.5),
        fuel_type=fuel_type,
        household_count=params.get("household_count", 1000),
        thermal_efficiency=params.get("thermal_efficiency", 0.30),
        baseline_efficiency=params.get("baseline_efficiency", 0.10),
        fnrb=fnrb_result["fnrb_value"],
        fnrb_uncertainty=fnrb_result["uncertainty_range"]["std_dev"],
        leakage_assessment=leakage_result,
    )

    # ─── Store Calculation Run ────────────────────────────────────────────────
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
    db.add(calc_run)
    await db.commit()
    await db.refresh(calc_run)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.calculation_run,
        actor_id=current_user.id,
        target_type="project",
        target_id=project_id,
    )

    logger.info(
        "calculation_completed",
        calc_id=str(calc_run.id),
        project_id=str(project_id),
        emissions_reduction=calc_run.emissions_reduction_tCO2e,
        methodology_score=methodology_result["compliance_score"],
    )

    return {
        "calculation_run_id": calc_run.id,
        "project_id": project_id,
        "fnrb": fnrb_result,
        "emissions": emissions_result,
        "leakage": leakage_result,
        "methodology_validation": methodology_result,
        "uncertainty": uncertainty_result,
        "status": "draft",
        "message": "Calculation completed. Awaiting human approval before issuance.",
    }


@router.get("/{calc_id}/sensitivity")
async def get_calculation_sensitivity(
    calc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """Get tornado sensitivity analysis for a calculation run."""
    result = await db.execute(select(CalculationRun).where(CalculationRun.id == calc_id))
    calc = result.scalar_one_or_none()
    if not calc:
        raise HTTPException(status_code=404, detail="Calculation run not found")
    await require_project_access(calc.project_id, current_user, db)

    from app.calculations.uncertainty_engine import run_sensitivity_analysis

    sensitivity = run_sensitivity_analysis(
        fuel_consumption_kg_per_day=2.5,
        fuel_type="wood",
        household_count=1000,
        thermal_efficiency=0.30,
        baseline_efficiency=0.10,
        fnrb=calc.fNRB_value or 0.30,
        fnrb_uncertainty=0.10,
    )

    return {
        "calculation_run_id": calc_id,
        "sensitivity_analysis": sensitivity,
        "interpretation": (
            "Parameters ranked by impact on emission reductions. "
            "Focus data collection efforts on top-ranked parameters."
        ),
    }


@router.post("/{calc_id}/approve")
async def approve_calculation(
    calc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Human approval gate for calculation run."""
    result = await db.execute(select(CalculationRun).where(CalculationRun.id == calc_id))
    calc = result.scalar_one_or_none()
    if not calc:
        raise HTTPException(status_code=404, detail="Calculation run not found")

    await require_project_access(calc.project_id, current_user, db)

    # Verify at least one validated data source exists
    ds_result = await db.execute(
        select(DataSource).where(
            DataSource.project_id == calc.project_id,
            DataSource.validation_status == ValidationStatusEnum.valid,
        )
    )
    if not ds_result.scalars().first():
        raise HTTPException(status_code=400, detail="No validated data sources for this project")

    if calc.status.value == "approved":
        raise HTTPException(status_code=400, detail="Calculation already approved")

    calc.status = "approved"
    calc.approved_by = current_user.id
    await db.commit()
    await db.refresh(calc)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.report_approved,
        actor_id=current_user.id,
        target_type="calculation_run",
        target_id=calc.id,
    )

    logger.info("calculation_approved", calc_id=str(calc_id), approved_by=str(current_user.id))

    return {
        "calculation_run_id": calc_id,
        "status": "approved",
        "approved_by": current_user.id,
        "approved_at": calc.created_at.isoformat(),
        "message": "Calculation approved for report generation and submission.",
    }
