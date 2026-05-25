"""WhatsApp Business API webhook and bot endpoints."""

import os

from fastapi import APIRouter, Request, HTTPException, status, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import uuid

from app.database import get_db
from app.models import (
    Enumerator,
    SurveyResponse,
    SupportTicket,
    ValidationStatusEnum,
)
from app.auth.dependencies import require_operator, require_admin, require_viewer
from app.services.whatsapp.bot import get_whatsapp_bot
from app.services.whatsapp.meta_api import get_whatsapp_api
from app.services.whatsapp.state_machine import conversation_state
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["whatsapp"])

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
if not VERIFY_TOKEN:
    raise RuntimeError("WHATSAPP_VERIFY_TOKEN environment variable is required")


# ─── Meta Webhook Endpoints ───────────────────────────────────────────────────

@router.get("/whatsapp")
async def whatsapp_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Verify webhook subscription with Meta."""
    api = get_whatsapp_api()
    result = await api.verify_webhook(hub_mode, hub_verify_token, hub_challenge, VERIFY_TOKEN)
    if result:
        logger.info("whatsapp_webhook_verified")
        return PlainTextResponse(content=result)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/whatsapp")
async def whatsapp_webhook_receive(request: Request):
    """Receive incoming messages from Meta WhatsApp webhook."""
    try:
        payload = await request.json()
        logger.debug("whatsapp_webhook_payload", payload=payload)

        bot = get_whatsapp_bot()
        result = await bot.handle_message(payload)
        return {"status": "ok", "result": result}
    except Exception as exc:
        logger.error("whatsapp_webhook_error", error=str(exc))
        return {"status": "error", "detail": str(exc)}


# ─── Enumerator Management ────────────────────────────────────────────────────

@router.get("/enumerators", response_model=list)
async def list_enumerators(
    project_id: Optional[uuid.UUID] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_viewer),
):
    """List all enumerators with performance metrics."""
    stmt = select(Enumerator)
    if project_id:
        stmt = stmt.where(Enumerator.project_id == project_id)
    if active_only:
        stmt = stmt.where(Enumerator.active.is_(True))
    stmt = stmt.order_by(Enumerator.data_quality_score.desc().nullslast())

    result = await db.execute(stmt)
    enumerators = result.scalars().all()

    return [
        {
            "id": str(e.id),
            "name": e.name,
            "phone_number": e.phone_number,
            "language_preference": e.language_preference,
            "active": e.active,
            "data_quality_score": e.data_quality_score,
            "submissions_count": e.submissions_count,
            "rejections_count": e.rejections_count,
            "rejection_rate": round(e.rejections_count / max(e.submissions_count, 1) * 100, 1),
            "last_sync_at": e.last_sync_at.isoformat() if e.last_sync_at else None,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in enumerators
    ]


@router.post("/enumerators", status_code=status.HTTP_201_CREATED)
async def create_enumerator(
    project_id: uuid.UUID,
    name: str,
    phone_number: str,
    language_preference: str = "en",
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(require_operator),
):
    """Register a new enumerator for a project."""
    enumerator = Enumerator(
        project_id=project_id,
        name=name,
        phone_number=phone_number,
        language_preference=language_preference,
    )
    db.add(enumerator)
    await db.commit()
    await db.refresh(enumerator)

    logger.info("enumerator_created", enumerator_id=str(enumerator.id), phone=phone_number)
    return {
        "id": str(enumerator.id),
        "name": name,
        "phone_number": phone_number,
        "message": "Enumerator registered successfully. Share the bot link to begin surveys.",
    }


@router.get("/enumerators/{enumerator_id}/performance")
async def get_enumerator_performance(
    enumerator_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_viewer),
):
    """Get detailed performance metrics for an enumerator."""
    result = await db.execute(select(Enumerator).where(Enumerator.id == enumerator_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Enumerator not found")

    # Get survey stats
    survey_result = await db.execute(
        select(func.count(SurveyResponse.id)).where(SurveyResponse.enumerator_id == enumerator_id)
    )
    total_surveys = survey_result.scalar() or 0

    valid_result = await db.execute(
        select(func.count(SurveyResponse.id)).where(
            SurveyResponse.enumerator_id == enumerator_id,
            SurveyResponse.validation_status == ValidationStatusEnum.valid,
        )
    )
    valid_surveys = valid_result.scalar() or 0

    flagged_result = await db.execute(
        select(func.count(SurveyResponse.id)).where(
            SurveyResponse.enumerator_id == enumerator_id,
            SurveyResponse.validation_status == ValidationStatusEnum.flagged,
        )
    )
    flagged_surveys = flagged_result.scalar() or 0

    return {
        "enumerator_id": str(enumerator_id),
        "name": e.name,
        "phone_number": e.phone_number,
        "total_surveys": total_surveys,
        "valid_surveys": valid_surveys,
        "flagged_surveys": flagged_surveys,
        "rejection_rate": round(e.rejections_count / max(e.submissions_count, 1) * 100, 1),
        "data_quality_score": e.data_quality_score,
        "last_sync_at": e.last_sync_at.isoformat() if e.last_sync_at else None,
    }


# ─── Survey Responses ─────────────────────────────────────────────────────────

@router.get("/survey-responses")
async def list_survey_responses(
    project_id: Optional[uuid.UUID] = None,
    enumerator_id: Optional[uuid.UUID] = None,
    validation_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_viewer),
):
    """List survey responses with filtering."""
    stmt = select(SurveyResponse)
    if project_id:
        stmt = stmt.where(SurveyResponse.project_id == project_id)
    if enumerator_id:
        stmt = stmt.where(SurveyResponse.enumerator_id == enumerator_id)
    if validation_status:
        stmt = stmt.where(SurveyResponse.validation_status == validation_status)
    stmt = stmt.order_by(SurveyResponse.created_at.desc())

    result = await db.execute(stmt)
    responses = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "project_id": str(r.project_id),
            "enumerator_id": str(r.enumerator_id) if r.enumerator_id else None,
            "household_id": r.household_id,
            "stove_id": r.stove_id,
            "village_name": r.village_name,
            "gps": {"lat": r.gps_latitude, "lon": r.gps_longitude},
            "validation_status": r.validation_status.value,
            "confidence_score": r.confidence_score,
            "submitted_via": r.submitted_via,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in responses
    ]


# ─── Support Tickets ──────────────────────────────────────────────────────────

@router.get("/support-tickets")
async def list_support_tickets(
    project_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_viewer),
):
    """List support tickets."""
    stmt = select(SupportTicket)
    if project_id:
        stmt = stmt.where(SupportTicket.project_id == project_id)
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    stmt = stmt.order_by(SupportTicket.created_at.desc())

    result = await db.execute(stmt)
    tickets = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "phone_number": t.phone_number,
            "issue_type": t.issue_type,
            "description": t.description,
            "status": t.status,
            "assigned_to": str(t.assigned_to) if t.assigned_to else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tickets
    ]


# ─── Active Conversations ─────────────────────────────────────────────────────

@router.get("/conversations/active")
async def get_active_conversations(
    pattern: str = "*",
    _: str = Depends(require_admin),
):
    """Get list of active WhatsApp conversations from Redis."""
    phones = conversation_state.get_active_conversations(pattern)
    conversations = []
    for phone in phones:
        state = conversation_state.get_state(phone)
        conversations.append({
            "phone_number": phone,
            "flow": state.get("flow"),
            "step": state.get("step"),
            "language": state.get("language"),
            "message_count": state.get("message_count"),
            "updated_at": state.get("updated_at"),
        })
    return conversations


# ─── Bot Testing ──────────────────────────────────────────────────────────────

@router.post("/whatsapp/send")
async def send_whatsapp_message(
    phone_number: str,
    message: str,
    _: str = Depends(require_operator),
):
    """Send a test message via WhatsApp (for debugging)."""
    api = get_whatsapp_api()
    result = await api.send_text_message(phone_number, message)
    return result
