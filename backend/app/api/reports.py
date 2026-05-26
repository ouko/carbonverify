from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.database import get_db
from app.models import Report, Project, CalculationRun, User
from app.schemas import ReportCreate, ReportUpdate, ReportOut
from app.auth.dependencies import require_operator, require_viewer
from app.reports.quality_gates import run_quality_gates
from app.vvb_liaison.registry_clients.verra import VerraRegistryClient
from app.vvb_liaison.registry_clients.gold_standard import GoldStandardRegistryClient
from app.vvb_liaison.auto_responder import draft_clarification_response
from app.tasks.report_jobs import generate_report_async
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/", response_model=List[ReportOut])
async def list_reports(
    project_id: uuid.UUID = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Report)
    if project_id:
        stmt = stmt.where(Report.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    report = Report(**payload.model_dump())
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.patch("/{report_id}", response_model=ReportOut)
async def update_report(
    report_id: uuid.UUID,
    payload: ReportUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    await db.commit()
    await db.refresh(report)
    return report


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    await db.delete(report)
    await db.commit()
    return None


@router.post("/{report_id}/generate")
async def generate_report_endpoint(
    report_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Trigger async report generation for a report record."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Get associated project and calculation
    proj_result = await db.execute(select(Project).where(Project.id == report.project_id))
    project = proj_result.scalar_one_or_none()

    calc_result = await db.execute(select(CalculationRun).where(CalculationRun.id == report.calculation_run_id))
    calc_run = calc_result.scalar_one_or_none()

    if not project or not calc_run:
        raise HTTPException(status_code=400, detail="Project or calculation run not found")

    # Queue async generation
    generate_report_async.delay(str(report_id))

    logger.info("report_generation_queued", report_id=str(report_id), user_id=str(current_user.id))

    return {
        "report_id": report_id,
        "status": "queued",
        "message": "Report generation queued. You will be notified when complete.",
    }


@router.post("/{report_id}/quality-check")
async def run_report_quality_check(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Run automated quality gates on report draft content."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    calc_result = await db.execute(select(CalculationRun).where(CalculationRun.id == report.calculation_run_id))
    calc_run = calc_result.scalar_one_or_none()

    # Get draft HTML from report
    draft_html = report.draft_content.get("html", "") if report.draft_content else ""
    if not draft_html:
        raise HTTPException(status_code=400, detail="No draft content available for quality check")

    calc_data = {
        "emissions_reduction_tco2e": calc_run.emissions_reduction_tCO2e if calc_run else 0,
        "fNRB_value": calc_run.fNRB_value if calc_run else 0,
        "baseline_emissions": calc_run.leakage_assessment if calc_run else {},
    }

    quality_result = run_quality_gates(draft_html, calc_data, report.template_type.value)

    # Update report with quality results
    if report.draft_content is None:
        report.draft_content = {}
    report.draft_content["quality_gates"] = quality_result
    await db.commit()

    return {
        "report_id": report_id,
        "quality_check": quality_result,
    }


@router.post("/{report_id}/submit-to-registry")
async def submit_report_to_registry(
    report_id: uuid.UUID,
    registry: str,  # "verra" or "gold_standard"
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Submit a completed report to the specified registry."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    calc_result = await db.execute(select(CalculationRun).where(CalculationRun.id == report.calculation_run_id))
    calc_run = calc_result.scalar_one_or_none()

    report_data = {
        "monitoring_period_start": str(calc_run.monitoring_period_start) if calc_run else None,
        "monitoring_period_end": str(calc_run.monitoring_period_end) if calc_run else None,
        "emissions_reduction_tco2e": calc_run.emissions_reduction_tCO2e if calc_run else 0,
        "uncertainty_95CI": calc_run.uncertainty_95CI if calc_run else 0,
        "methodology": report.template_type.value,
        "documents": [{"url": report.final_pdf}] if report.final_pdf else [],
    }

    # Submit to registry
    if registry == "verra":
        client = VerraRegistryClient()
        registry_result = client.submit_monitoring_report(str(report.project_id), report_data)
        client.close()
    elif registry == "gold_standard":
        client = GoldStandardRegistryClient()
        registry_result = client.submit_monitoring_report(str(report.project_id), report_data)
        client.close()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported registry: {registry}")

    # Update report status
    if registry_result.get("success"):
        report.status = "submitted"
    else:
        report.status = "draft"
        report.draft_content = report.draft_content or {}
        report.draft_content["registry_submission_error"] = registry_result.get("error")

    await db.commit()

    return {
        "report_id": report_id,
        "registry": registry,
        "submission_result": registry_result,
    }


@router.post("/{report_id}/draft-clarification-response")
async def draft_clarification(
    report_id: uuid.UUID,
    query_text: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Auto-draft a response to a VVB technical query."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    proj_result = await db.execute(select(Project).where(Project.id == report.project_id))
    project = proj_result.scalar_one_or_none()

    calc_result = await db.execute(select(CalculationRun).where(CalculationRun.id == report.calculation_run_id))
    calc_run = calc_result.scalar_one_or_none()

    project_data = {
        "name": project.name if project else "Unknown",
        "kpt_sample_size": 35,
        "kpt_duration_weeks": 3,
        "thermal_efficiency": 0.30,
        "baseline_efficiency": 0.10,
        "lab_test_type": "WBT",
        "test_lab": "Test Lab",
        "usage_rate": 0.85,
        "usage_monitoring_method": "field_training",
        "stacking_rate": 0.05,
    }

    calc_data = {
        "fNRB_value": calc_run.fNRB_value if calc_run else 0.30,
        "source_reference": "Spatial interpolation",
        "uncertainty_range": {"lower": 0.20, "upper": 0.40, "std_dev": 0.10},
        "emissions_reduction_tco2e": calc_run.emissions_reduction_tCO2e if calc_run else 0,
        "leakage_tco2e": 0.03,
        "leakage_assessment": {"leakage_as_pct_of_baseline": 2.5, "buffer_recommendation_pct": 10},
        "monte_carlo": {
            "n_iterations": 10000,
            "uncertainty_95ci": {"lower": 1000, "upper": 1500},
            "conservative_estimate_tco2e": 1000,
        },
    }

    response = draft_clarification_response(
        query_text=query_text,
        project_data=project_data,
        calculation_data=calc_data,
        methodology=report.template_type.value,
    )

    return {
        "report_id": report_id,
        "query": query_text,
        "draft_response": response,
    }
