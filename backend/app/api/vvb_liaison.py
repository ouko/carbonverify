import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.models import Report, Project, CalculationRun, User, AuditActionEnum
from app.auth.dependencies import require_operator
from app.security.audit_logging import AuditLogger
from app.vvb_liaison.polling import RegistryPoller
from app.vvb_liaison.auto_responder import draft_clarification_response
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/vvb", tags=["vvb-liaison"])


@router.post("/poll/{registry}")
async def poll_registry(
    registry: str,  # "verra", "gold_standard", "kenya_national"
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Manually poll a registry for project status."""
    poller = RegistryPoller()
    result = poller.poll_project(registry, str(project_id))
    poller.close()
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.vvb_submitted,
        actor_id=current_user.id,
        target_type="project",
        target_id=project_id,
        metadata={"event": "registry_poll", "registry": registry},
    )
    return result


@router.post("/draft-response/{report_id}")
async def draft_vvb_response(
    report_id: uuid.UUID,
    query_text: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Draft a response to a VVB technical query."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    proj_result, calc_result = await asyncio.gather(
        db.execute(select(Project).where(Project.id == report.project_id)),
        db.execute(select(CalculationRun).where(CalculationRun.id == report.calculation_run_id)),
    )
    project = proj_result.scalar_one_or_none()
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

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.vvb_responded,
        actor_id=current_user.id,
        target_type="report",
        target_id=report_id,
        metadata={"event": "draft_vvb_response"},
    )
    return {
        "report_id": report_id,
        "query": query_text,
        "draft_response": response,
    }


@router.get("/follow-up-drafts")
async def get_follow_up_drafts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Get all reports needing follow-up with email drafts."""
    from datetime import datetime, timezone
    from app.vvb_liaison.polling import generate_follow_up_email

    result = await db.execute(select(Report).where(Report.status == "submitted"))
    reports = result.scalars().all()

    # Filter to pending reports first
    pending_reports = []
    for report in reports:
        submitted_at = report.draft_content.get("submitted_at") if report.draft_content else None
        if not submitted_at:
            continue
        submitted_date = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
        days_pending = (datetime.now(timezone.utc) - submitted_date).days
        if days_pending >= 14:
            pending_reports.append((report, days_pending))

    # Batch-load projects and calculation runs to avoid N+1
    project_ids = {r.project_id for r, _ in pending_reports if r.project_id}
    calc_ids = {r.calculation_run_id for r, _ in pending_reports if r.calculation_run_id}

    projects = {}
    if project_ids:
        proj_result = await db.execute(select(Project).where(Project.id.in_(project_ids)))
        for p in proj_result.scalars().all():
            projects[p.id] = p

    calc_runs = {}
    if calc_ids:
        calc_result = await db.execute(select(CalculationRun).where(CalculationRun.id.in_(calc_ids)))
        for c in calc_result.scalars().all():
            calc_runs[c.id] = c

    drafts = []
    for report, days_pending in pending_reports:
        project = projects.get(report.project_id)
        calc_run = calc_runs.get(report.calculation_run_id)

        email = generate_follow_up_email(
            project_name=project.name if project else "Unknown",
            registry_name="Verra" if "VM" in report.template_type.value else "Gold Standard",
            report_id=str(report.id),
            current_status="Under Review",
            days_pending=days_pending,
            emissions_reduction=calc_run.emissions_reduction_tCO2e if calc_run else 0,
            monitoring_period_start=str(calc_run.monitoring_period_start) if calc_run else "N/A",
            monitoring_period_end=str(calc_run.monitoring_period_end) if calc_run else "N/A",
            methodology=report.template_type.value,
            compliance_score=calc_run.methodology_compliance_score if calc_run else 0,
        )

        drafts.append({
            "report_id": str(report.id),
            "project_name": project.name if project else "Unknown",
            "days_pending": days_pending,
            "email_draft": email,
        })

    return {"drafts": drafts}
