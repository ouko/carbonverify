import uuid
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Project, DataSource, SourceTypeEnum, ValidationStatusEnum, User
from app.schemas import IoTWebhookPayload, IoTWebhookResponse
from app.auth.dependencies import get_current_user, require_operator
from app.services.pipelines.iot import process_iot_webhook
from app.services.validation_engine import run_full_validation
from app.services.provenance import build_full_provenance
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/iot/{project_id}", response_model=IoTWebhookResponse)
async def receive_iot_webhook(
    project_id: uuid.UUID,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    # Validate project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info("iot_webhook_received", project_id=str(project_id), payload_keys=list(payload.keys()))

    # Process IoT payload
    processing_result = process_iot_webhook(payload)
    normalized = processing_result["normalized"]

    # Run validation engine
    validation = run_full_validation(
        data=processing_result,
        data_type="iot",
        project_confidence_threshold=project.confidence_threshold,
        monitoring_period_start=project.crediting_period_start,
        monitoring_period_end=project.crediting_period_end,
    )

    # Determine validation status
    if validation["status"] == "valid":
        validation_status = ValidationStatusEnum.valid
    elif validation["needs_human_review"]:
        validation_status = ValidationStatusEnum.flagged
    else:
        validation_status = ValidationStatusEnum.pending

    # Build provenance
    provenance = build_full_provenance(
        raw_source=f"iot_webhook:{project_id}",
        processing_pipeline="iot_webhook_pipeline",
        processing_result=processing_result,
        validation_result=validation,
    )

    # Store as data source
    data_source = DataSource(
        project_id=project_id,
        source_type=SourceTypeEnum.iot,
        schema_version="iot_v1",
        raw_data=payload,
        processed_data=normalized,
        validation_status=validation_status,
        validation_errors=validation["validation_errors"] or None,
        provenance=provenance,
        confidence_score=validation["confidence_score"],
    )
    db.add(data_source)
    await db.commit()
    await db.refresh(data_source)

    # Auto-flag for human review if needed
    if validation["needs_human_review"]:
        from app.models import HumanReviewQueue, QueueItemTypeEnum, QueueStatusEnum
        review_item = HumanReviewQueue(
            item_type=QueueItemTypeEnum.data_anomaly,
            item_id=data_source.id,
            reason=f"IoT data confidence {validation['confidence_score']:.2f} below threshold {project.confidence_threshold}",
            priority=3,
            status=QueueStatusEnum.pending,
        )
        db.add(review_item)
        await db.commit()

    logger.info(
        "iot_webhook_processed",
        project_id=str(project_id),
        data_source_id=str(data_source.id),
        validation_status=validation_status.value,
        confidence=validation["confidence_score"],
    )

    return IoTWebhookResponse(
        received=True,
        data_source_id=data_source.id,
        validation_status=validation_status.value,
        confidence_score=validation["confidence_score"],
        errors=validation["validation_errors"] or None,
    )
