import asyncio
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.tasks.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import (
    DataSource, Project, CalculationRun, Report, FileUpload,
    FileUploadStatusEnum, SourceTypeEnum, ValidationStatusEnum,
    HumanReviewQueue, QueueItemTypeEnum, QueueStatusEnum,
)
from app.services.pipelines.excel_csv import process_excel_csv
from app.services.pipelines.pdf import process_pdf
from app.services.pipelines.image import process_image
from app.services.validation_engine import run_full_validation
from app.services.provenance import build_full_provenance
from app.core.logging import get_logger

logger = get_logger(__name__)


def run_async(coro):
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
def check_flagged_data_sources(self):
    logger.info("task_check_flagged_data_sources_started")

    async def _check():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DataSource).where(DataSource.validation_status == "flagged")
            )
            flagged = result.scalars().all()
            for ds in flagged:
                logger.info("flagged_data_source_found", ds_id=str(ds.id), project_id=str(ds.project_id))
            return len(flagged)

    try:
        count = run_async(_check())
        logger.info("task_check_flagged_data_sources_completed", count=count)
        return {"checked": count}
    except Exception as exc:
        logger.error("task_check_flagged_data_sources_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def generate_overdue_reports(self):
    logger.info("task_generate_overdue_reports_started")

    async def _generate():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Project).where(Project.status == "calculation")
            )
            projects = result.scalars().all()
            for project in projects:
                logger.info("overdue_report_project", project_id=str(project.id))
            return len(projects)

    try:
        count = run_async(_generate())
        logger.info("task_generate_overdue_reports_completed", count=count)
        return {"overdue_projects": count}
    except Exception as exc:
        logger.error("task_generate_overdue_reports_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task
def process_data_source_validation(ds_id: str):
    logger.info("task_process_ds_validation_started", ds_id=ds_id)

    async def _process():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
            ds = result.scalar_one_or_none()
            if not ds:
                return {"error": "not found"}
            ds.validation_status = "valid"
            await db.commit()
            return {"ds_id": ds_id, "status": "valid"}

    return run_async(_process())


@celery_app.task(bind=True, max_retries=3)
def generate_report_async(self, report_id: str):
    """Generate a report PDF asynchronously."""
    logger.info("task_generate_report_started", report_id=report_id)

    async def _generate():
        async with AsyncSessionLocal() as db:
            from app.models import Report
            result = await db.execute(select(Report).where(Report.id == report_id))
            report = result.scalar_one_or_none()
            if not report:
                return {"error": "report not found"}
            # Placeholder: actual PDF generation would happen here
            report.status = "approved"
            await db.commit()
            return {"report_id": report_id, "status": "generated"}

    try:
        return run_async(_generate())
    except Exception as exc:
        logger.error("generate_report_failed", report_id=report_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def process_uploaded_file(self, upload_id: str):
    """Process an uploaded file based on its detected type."""
    logger.info("task_process_upload_started", upload_id=upload_id)

    async def _process():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(FileUpload).where(FileUpload.id == upload_id))
            upload = result.scalar_one_or_none()
            if not upload:
                return {"error": "upload not found"}

            # Update status
            upload.status = FileUploadStatusEnum.processing
            await db.commit()

            # Get project for validation context
            project_result = await db.execute(select(Project).where(Project.id == upload.project_id))
            project = project_result.scalar_one_or_none()

            # Download file from S3
            try:
                import boto3
                from app.config import get_settings
                settings = get_settings()
                s3 = boto3.client(
                    "s3",
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
                )
                s3_obj = s3.get_object(Bucket=upload.s3_bucket, Key=upload.s3_key)
                file_bytes = s3_obj["Body"].read()
            except Exception as e:
                logger.error("s3_download_failed", upload_id=upload_id, error=str(e))
                upload.status = FileUploadStatusEnum.failed
                upload.validation_errors = [f"Failed to download from S3: {str(e)}"]
                await db.commit()
                return {"error": "s3 download failed"}

            detected_type = upload.detected_type.value
            processing_result = None

            try:
                if detected_type in ("excel", "csv"):
                    processing_result = process_excel_csv(file_bytes, detected_type, upload.original_filename)
                elif detected_type == "pdf":
                    processing_result = process_pdf(file_bytes, upload.original_filename)
                elif detected_type == "image":
                    processing_result = process_image(
                        file_bytes,
                        upload.original_filename,
                        project_boundary=None,  # Could load from project metadata
                        monitoring_period_start=project.crediting_period_start if project else None,
                        monitoring_period_end=project.crediting_period_end if project else None,
                    )
                else:
                    upload.status = FileUploadStatusEnum.failed
                    upload.validation_errors = [f"Unsupported file type: {detected_type}"]
                    await db.commit()
                    return {"error": "unsupported file type"}
            except Exception as e:
                logger.error("pipeline_processing_failed", upload_id=upload_id, error=str(e))
                upload.status = FileUploadStatusEnum.failed
                upload.validation_errors = [f"Processing failed: {str(e)}"]
                await db.commit()
                return {"error": str(e)}

            # Run validation engine
            validation = run_full_validation(
                data=processing_result,
                data_type=detected_type,
                project_confidence_threshold=project.confidence_threshold if project else 0.85,
                monitoring_period_start=project.crediting_period_start if project else None,
                monitoring_period_end=project.crediting_period_end if project else None,
            )

            # Update upload record
            upload.processing_result = processing_result
            upload.confidence_score = validation["confidence_score"]
            upload.validation_errors = validation["validation_errors"] or None
            upload.status = FileUploadStatusEnum.completed
            upload.processed_at = datetime.utcnow()

            # Build provenance
            upload.provenance = build_full_provenance(
                file_bytes=file_bytes,
                original_filename=upload.original_filename,
                detected_type=detected_type,
                processing_pipeline=f"{detected_type}_pipeline",
                processing_result=processing_result,
                validation_result=validation,
                s3_key=upload.s3_key,
            )

            await db.commit()

            # Create data source record
            source_type = SourceTypeEnum.document
            if detected_type in ("excel", "csv"):
                source_type = SourceTypeEnum.manual_entry
            elif detected_type == "image":
                source_type = SourceTypeEnum.mobile_survey

            data_source = DataSource(
                project_id=upload.project_id,
                source_type=source_type,
                schema_version=f"{detected_type}_v1",
                raw_data={"upload_id": str(upload.id), "filename": upload.original_filename},
                processed_data=processing_result,
                validation_status=ValidationStatusEnum.valid if validation["status"] == "valid" else ValidationStatusEnum.flagged,
                validation_errors=validation["validation_errors"] or None,
                provenance=upload.provenance,
                confidence_score=validation["confidence_score"],
            )
            db.add(data_source)
            await db.commit()
            await db.refresh(data_source)

            # Auto-flag for human review if confidence below threshold
            if validation["needs_human_review"]:
                review_item = HumanReviewQueue(
                    item_type=QueueItemTypeEnum.data_anomaly,
                    item_id=data_source.id,
                    reason=f"File upload confidence {validation['confidence_score']:.2f} below threshold {project.confidence_threshold if project else 0.85}",
                    priority=3,
                    status=QueueStatusEnum.pending,
                )
                db.add(review_item)
                await db.commit()

            logger.info(
                "upload_processed",
                upload_id=upload_id,
                data_source_id=str(data_source.id),
                detected_type=detected_type,
                confidence=validation["confidence_score"],
            )

            return {
                "upload_id": upload_id,
                "data_source_id": str(data_source.id),
                "detected_type": detected_type,
                "confidence_score": validation["confidence_score"],
                "status": upload.status.value,
            }

    try:
        return run_async(_process())
    except Exception as exc:
        logger.error("process_upload_failed", upload_id=upload_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)
