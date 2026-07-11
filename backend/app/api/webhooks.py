import asyncio
import uuid
import json
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Project, DataSource, SourceTypeEnum, ValidationStatusEnum
from app.schemas import IoTWebhookResponse
from app.services.pipelines.iot import process_iot_webhook
from app.services.validation_engine import run_full_validation
from app.services.provenance import build_full_provenance
from app.config import get_settings
from app.core.logging import get_logger
from app.security.webhook_security import (
    check_replay_protection,
    verify_hmac_signature,
    build_request_identifier,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()


def _require_iot_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Validate IoT webhook API key."""
    if not settings.IOT_WEBHOOK_API_KEY:
        logger.error("iot_webhook_api_key_not_configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook authentication not configured",
        )
    if x_api_key != settings.IOT_WEBHOOK_API_KEY:
        logger.warning("iot_webhook_invalid_api_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key


async def _require_iot_signature(request: Request) -> None:
    """Validate HMAC-SHA256 signature if a webhook secret is configured."""
    if not settings.IOT_WEBHOOK_SECRET:
        return
    body = await request.body()
    signature = request.headers.get("X-Signature", "")
    if not signature:
        logger.warning("iot_webhook_missing_signature")
        raise HTTPException(status_code=401, detail="Missing signature")
    if not verify_hmac_signature(body, settings.IOT_WEBHOOK_SECRET, signature):
        logger.warning("iot_webhook_invalid_signature")
        raise HTTPException(status_code=403, detail="Invalid signature")


async def _require_iot_replay_protection(request: Request) -> None:
    """Reject replayed requests using X-Request-ID."""
    request_id = request.headers.get("X-Request-ID", "")
    if not request_id:
        logger.warning("iot_webhook_missing_request_id")
        raise HTTPException(status_code=401, detail="Missing request ID")
    identifier = build_request_identifier(request_id)
    is_fresh = await check_replay_protection(identifier, ttl_seconds=300)
    if not is_fresh:
        logger.warning("iot_webhook_replay_detected", request_id=request_id[:16])
        raise HTTPException(status_code=403, detail="Replay detected")


@router.post("/iot/{project_id}", response_model=IoTWebhookResponse)
async def receive_iot_webhook(
    project_id: uuid.UUID,
    payload: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(_require_iot_api_key),
    _signature: None = Depends(_require_iot_signature),
    _replay: None = Depends(_require_iot_replay_protection),
):
    # Validate project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info("iot_webhook_received", project_id=str(project_id), payload_keys=list(payload.keys()))

    # Process IoT payload
    processing_result = await asyncio.to_thread(process_iot_webhook, payload)
    normalized = processing_result["normalized"]

    # Run validation engine
    validation = await asyncio.to_thread(
        run_full_validation,
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
