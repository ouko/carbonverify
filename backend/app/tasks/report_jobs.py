"""Celery tasks for report generation and VVB liaison."""

from datetime import datetime, timedelta
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.tasks.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import Report, Project, CalculationRun, DataSource, HumanReviewQueue, QueueItemTypeEnum, QueueStatusEnum
from app.reports.generator import generate_report
from app.vvb_liaison.polling import RegistryPoller, generate_follow_up_email
from app.vvb_liaison.registry_clients.verra import VerraRegistryClient
from app.vvb_liaison.registry_clients.gold_standard import GoldStandardRegistryClient
from app.core.logging import get_logger

logger = get_logger(__name__)


def run_async(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


@celery_app.task(bind=True, max_retries=3)
def generate_report_async(self, report_id: str):
    """Generate report HTML and PDF asynchronously."""
    logger.info("task_generate_report_started", report_id=report_id)

    async def _generate():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Report).where(Report.id == report_id))
            report = result.scalar_one_or_none()
            if not report:
                return {"error": "report not found"}

            # Get project
            proj_result = await db.execute(select(Project).where(Project.id == report.project_id))
            project = proj_result.scalar_one_or_none()

            # Get calculation run
            calc_result = await db.execute(select(CalculationRun).where(CalculationRun.id == report.calculation_run_id))
            calc_run = calc_result.scalar_one_or_none()

            # Get data sources
            ds_result = await db.execute(
                select(DataSource).where(DataSource.project_id == report.project_id)
            )
            data_sources = ds_result.scalars().all()

            # Convert ORM objects to dicts for generator
            project_dict = {
                "id": str(project.id),
                "name": project.name,
                "methodology": project.methodology.value,
                "crediting_period_start": project.crediting_period_start,
                "crediting_period_end": project.crediting_period_end,
                "confidence_threshold": project.confidence_threshold,
            } if project else {}

            calc_dict = {
                "id": str(calc_run.id),
                "fNRB_value": calc_run.fNRB_value,
                "emissions_reduction_tCO2e": calc_run.emissions_reduction_tCO2e,
                "uncertainty_95CI": calc_run.uncertainty_95CI,
                "leakage_assessment": calc_run.leakage_assessment,
                "monitoring_period_start": calc_run.monitoring_period_start,
                "monitoring_period_end": calc_run.monitoring_period_end,
            } if calc_run else {}

            ds_dicts = []
            for ds in data_sources:
                ds_dicts.append({
                    "id": str(ds.id),
                    "source_type": ds.source_type.value,
                    "schema_version": ds.schema_version,
                    "validation_status": ds.validation_status.value,
                    "record_count": ds.processed_data.get("total_rows") if ds.processed_data else None,
                })

            # Generate report
            methodology = report.template_type.value
            result = generate_report(project_dict, calc_dict, ds_dicts, methodology)

            # Update report
            report.draft_content = report.draft_content or {}
            report.draft_content["html"] = result["html"]
            report.draft_content["quality_gates"] = result["quality_gates"]
            report.draft_content["generated_at"] = result["generated_at"]

            if result["quality_gates"]["passed"]:
                report.status = "approved"  # Auto-approved if quality gates pass
            else:
                report.status = "human_review"
                # Add to human review queue
                review_item = HumanReviewQueue(
                    item_type=QueueItemTypeEnum.report,
                    item_id=report.id,
                    reason=f"Report quality gates failed: {'; '.join(result['quality_gates']['issues'][:3])}",
                    priority=3,
                    status=QueueStatusEnum.pending,
                )
                db.add(review_item)

            await db.commit()

            logger.info(
                "task_generate_report_completed",
                report_id=report_id,
                status=report.status.value,
                quality_passed=result["quality_gates"]["passed"],
            )

            return {
                "report_id": report_id,
                "status": report.status.value,
                "quality_passed": result["quality_gates"]["passed"],
                "pdf_path": result["pdf_path"],
            }

    try:
        return run_async(_generate())
    except Exception as exc:
        logger.error("generate_report_failed", report_id=report_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task
def poll_registry_statuses():
    """Poll all registries for project status updates."""
    logger.info("task_poll_registries_started")

    async def _poll():
        async with AsyncSessionLocal() as db:
            # Get all reports with status "submitted"
            result = await db.execute(
                select(Report).where(Report.status == "submitted")
            )
            submitted_reports = result.scalars().all()

            if not submitted_reports:
                return {"checked": 0, "changes": 0}

            poller = RegistryPoller()
            changes = 0

            for report in submitted_reports:
                # Determine registry from template type
                registry = "verra" if "VM" in report.template_type.value else "gold_standard"
                project_id = str(report.project_id)

                status_result = poller.poll_project(registry, project_id)

                if status_result.get("success") and status_result.get("status_changed"):
                    changes += 1
                    # Update report status based on registry status
                    new_status = status_result.get("verification_status", "submitted")
                    status_mapping = {
                        "verified": "vvb_approved",
                        "approved": "vvb_approved",
                        "rejected": "rejected",
                    }
                    report.status = status_mapping.get(new_status, "submitted")

                    # Add to review queue if rejected
                    if report.status == "rejected":
                        review_item = HumanReviewQueue(
                            item_type=QueueItemTypeEnum.vvb_response,
                            item_id=report.id,
                            reason=f"Report rejected by {registry}: {status_result.get('raw_response', {})}",
                            priority=5,
                            status=QueueStatusEnum.pending,
                        )
                        db.add(review_item)

            await db.commit()
            poller.close()

            logger.info("task_poll_registries_completed", checked=len(submitted_reports), changes=changes)
            return {"checked": len(submitted_reports), "changes": changes}

    return run_async(_poll())


@celery_app.task
def send_registry_follow_ups():
    """Check for reports needing follow-up and generate email drafts."""
    logger.info("task_follow_ups_started")

    async def _check():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Report).where(Report.status == "submitted")
            )
            submitted_reports = result.scalars().all()

            follow_ups_needed = []

            for report in submitted_reports:
                # Get submission date from report metadata
                submitted_at = report.draft_content.get("submitted_at") if report.draft_content else None
                if not submitted_at:
                    continue

                submitted_date = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
                days_pending = (datetime.utcnow() - submitted_date).days

                if days_pending >= 14:
                    proj_result = await db.execute(select(Project).where(Project.id == report.project_id))
                    project = proj_result.scalar_one_or_none()

                    calc_result = await db.execute(select(CalculationRun).where(CalculationRun.id == report.calculation_run_id))
                    calc_run = calc_result.scalar_one_or_none()

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

                    follow_ups_needed.append({
                        "report_id": str(report.id),
                        "project_id": str(report.project_id),
                        "days_pending": days_pending,
                        "email_draft": email,
                    })

            logger.info("task_follow_ups_completed", drafts=len(follow_ups_needed))
            return {"drafts_generated": len(follow_ups_needed), "drafts": follow_ups_needed}

    return run_async(_check())
