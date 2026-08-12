"""Lead Intelligence API routes."""

import asyncio
from typing import List, Optional
import uuid
from datetime import datetime, timezone, date as dt_date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Lead, User, LeadDocument, LeadRegistrySourceEnum, LeadPriorityEnum, LeadWorkflowStatusEnum, ScraperRun, AuditActionEnum
from app.schemas import (
    LeadCreate,
    LeadUpdate,
    LeadOut,
    LeadDocumentOut,
    LeadStats,
    LeadScrapeRequest,
    LeadBulkImportRequest,
    LeadBulkImportResponse,
    ProjectPreAuditOut,
)
from app.security.audit_logging import AuditLogger
from app.auth.dependencies import require_operator, require_viewer, require_admin
from app.services.lead_intelligence.scorer import score_lead, priority_from_score
from app.services.lead_intelligence.factory import get_scraper, list_scrapers, health_check_all
from app.services.lead_intelligence.lead_converter import LeadToProjectConverter, LeadConversionError
from app.services.lead_intelligence.pre_audit_runner import PreAuditRunner
from app.tasks.pre_audit_jobs import fetch_lead_documents as fetch_lead_documents_task
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("/", response_model=List[LeadOut])
async def list_leads(
    registry_source: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    lead_status: Optional[str] = Query(None),
    assigned_to: Optional[uuid.UUID] = Query(None),
    min_stuck_score: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Lead)
    if registry_source:
        stmt = stmt.where(Lead.registry_source == registry_source)
    if country:
        country_clean = country[:100].replace("%", "\\%").replace("_", "\\_")
        country_pattern = "%" + country_clean + "%"
        stmt = stmt.where(Lead.country.ilike(country_pattern))
    if priority:
        stmt = stmt.where(Lead.priority == priority)
    if lead_status:
        stmt = stmt.where(Lead.lead_status == lead_status)
    if assigned_to:
        stmt = stmt.where(Lead.assigned_to == assigned_to)
    if min_stuck_score is not None:
        stmt = stmt.where(Lead.stuck_score >= min_stuck_score)
    if search:
        search_clean = search[:100].replace("%", "\\%").replace("_", "\\_")
        search_pattern = "%" + search_clean + "%"
        stmt = stmt.where(Lead.project_name.ilike(search_pattern))

    stmt = stmt.order_by(Lead.stuck_score.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    lead = Lead(**payload.model_dump())
    lead.scraped_at = datetime.now(timezone.utc)
    lead.updated_at = datetime.now(timezone.utc)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_created,
        actor_id=current_user.id,
        target_type="lead",
        target_id=lead.id,
    )
    return lead


@router.post("/bulk-import", response_model=LeadBulkImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def bulk_import_leads(
    payload: LeadBulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Import a list of registry external IDs and queue document fetching.

    Consultants use this to seed CarbonVerify with projects they want to
    evaluate. Each lead is created (or updated if it already exists) and a
    document-fetch task is queued. The nightly pre-audit pipeline will later
    convert qualified leads and run AI pre-audit; or call
    `POST /leads/{lead_id}/convert-and-pre-audit` for an immediate result.
    """
    try:
        registry_source_enum = LeadRegistrySourceEnum(payload.registry_source)
    except ValueError:
        valid_sources = [e.value for e in LeadRegistrySourceEnum]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid registry_source. Valid values: {valid_sources}",
        )

    external_ids = [item.external_id for item in payload.items]
    if len(external_ids) != len(set(external_ids)):
        raise HTTPException(status_code=400, detail="Duplicate external_ids in request")

    existing_result = await db.execute(
        select(Lead).where(
            Lead.registry_source == registry_source_enum,
            Lead.external_id.in_(external_ids),
        )
    )
    existing_leads = {lead.external_id: lead for lead in existing_result.scalars().all()}

    created = 0
    updated = 0
    errors = 0
    lead_ids: List[uuid.UUID] = []

    for item in payload.items:
        try:
            lead = existing_leads.get(item.external_id)
            if lead:
                if item.project_name is not None:
                    lead.project_name = item.project_name
                if item.registry_url is not None:
                    lead.registry_url = item.registry_url
                if item.status is not None:
                    lead.status = item.status
                lead.updated_at = datetime.now(timezone.utc)
                updated += 1
            else:
                lead = Lead(
                    registry_source=registry_source_enum,
                    external_id=item.external_id,
                    project_name=item.project_name or item.external_id,
                    registry_url=item.registry_url,
                    status=item.status or "unknown",
                    lead_status=LeadWorkflowStatusEnum.new,
                    scraped_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(lead)
                created += 1
            await db.flush()
            await db.refresh(lead)
            lead_ids.append(lead.id)
            existing_leads[item.external_id] = lead
        except Exception as exc:
            logger.error("bulk_import_lead_failed", external_id=item.external_id, error=str(exc))
            errors += 1

    await db.commit()

    for lead_id in lead_ids:
        fetch_lead_documents_task.delay(str(lead_id))

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.data_ingested,
        actor_id=current_user.id,
        target_type="lead",
        target_id=None,
        metadata={
            "event": "bulk_import",
            "registry_source": registry_source_enum.value,
            "created": created,
            "updated": updated,
            "queued": len(lead_ids),
            "errors": errors,
        },
    )

    return LeadBulkImportResponse(
        registry_source=registry_source_enum.value,
        created=created,
        updated=updated,
        queued=len(lead_ids),
        errors=errors,
        leads=lead_ids,
    )


@router.get("/scraper-history")
async def get_scraper_history(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Return the most recent scrape run for each registry source."""
    from sqlalchemy import desc

    results = {}
    for source in list_scrapers():
        run_result = await db.execute(
            select(ScraperRun)
            .where(ScraperRun.source == source)
            .order_by(desc(ScraperRun.scraped_at))
            .limit(1)
        )
        run = run_result.scalar_one_or_none()
        if run:
            results[source] = {
                "scraped_at": run.scraped_at.isoformat() if run.scraped_at else None,
                "count": run.count,
                "created": run.created,
                "updated": run.updated,
                "status": run.status,
                "data_source": run.data_source,
                "error_message": run.error_message,
                "mode": run.mode,
            }
        else:
            results[source] = None

    return results


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.get("/{lead_id}/documents", response_model=List[LeadDocumentOut])
async def get_lead_documents(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    result = await db.execute(
        select(LeadDocument).where(LeadDocument.lead_id == lead_id).order_by(LeadDocument.created_at)
    )
    return result.scalars().all()


@router.post("/{lead_id}/fetch-documents", status_code=202)
async def fetch_lead_documents(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    fetch_lead_documents_task.delay(str(lead_id))
    return {"message": "Document fetch queued", "lead_id": str(lead_id)}


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)

    lead.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(lead)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="lead",
        target_id=lead.id,
    )
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.delete(lead)
    await db.commit()
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="lead",
        target_id=lead.id,
        metadata={"event": "lead_deleted"},
    )


@router.post("/{lead_id}/score", response_model=LeadOut)
async def score_single_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.stuck_score = score_lead(
        days_in_status=lead.days_in_status,
        status=lead.status.value if hasattr(lead.status, "value") else str(lead.status),
        crediting_period_end=lead.crediting_period_end,
        last_verification_date=lead.last_verification_date,
        methodology=lead.methodology,
    )
    lead.priority = priority_from_score(lead.stuck_score)
    lead.last_scored_at = datetime.now(timezone.utc)
    lead.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(lead)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="lead",
        target_id=lead.id,
        metadata={"event": "lead_scored"},
    )
    return lead


async def _scrape_one(source: str, country: str) -> tuple[str, list[dict], str | None]:
    """Scrape a single registry source. Returns (source, leads, error)."""
    scraper = get_scraper(source)
    try:
        raw_leads = await asyncio.wait_for(
            asyncio.to_thread(scraper.scrape, country=country),
            timeout=90.0,
        )
        return source, raw_leads, None
    except asyncio.TimeoutError:
        logger.warning("scrape_timeout", source=source, country=country)
        return source, [], "Scrape timed out after 90s"
    except Exception as exc:
        logger.error("scrape_failed", source=source, error=str(exc))
        return source, [], str(exc)
    finally:
        scraper.close()


@router.post("/scrape")
async def trigger_scrape(
    payload: LeadScrapeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    sources = [payload.registry_source] if payload.registry_source else list_scrapers()
    country = payload.country or "Kenya"

    # Run all scrapers concurrently
    scrape_tasks = [_scrape_one(source, country) for source in sources]
    scrape_results = await asyncio.gather(*scrape_tasks)

    total_created = 0
    total_updated = 0
    per_source: list[dict] = []

    for source, raw_leads, error_msg in scrape_results:
        data_source = "demo"
        source_created = 0
        source_updated = 0

        # Batch-load existing leads to avoid N+1 queries per raw lead
        external_ids = [raw["external_id"] for raw in raw_leads if "external_id" in raw]
        existing_leads = {}
        if external_ids:
            existing_result = await db.execute(
                select(Lead).where(
                    Lead.registry_source == source,
                    Lead.external_id.in_(external_ids),
                )
            )
            for lead in existing_result.scalars().all():
                existing_leads[lead.external_id] = lead

        for raw in raw_leads:
            meta = raw.pop("_scrape_meta", {})
            data_source = meta.get("data_source", "demo")

            lead = existing_leads.get(raw.get("external_id"))

            # Compute score
            cp_end = None
            if raw.get("crediting_period_end"):
                cp_end = dt_date.fromisoformat(raw["crediting_period_end"])
            lv_date = None
            if raw.get("last_verification_date"):
                lv_date = dt_date.fromisoformat(raw["last_verification_date"])

            stuck = score_lead(
                days_in_status=raw.get("days_in_status"),
                status=raw.get("status", "unknown"),
                crediting_period_end=cp_end,
                last_verification_date=lv_date,
                methodology=raw.get("methodology"),
            )
            priority = priority_from_score(stuck)

            if lead:
                for key in ["project_name", "project_developer", "developer_contact",
                            "developer_email", "country", "region", "methodology", "sector",
                            "status", "estimated_credits_per_year", "registry_url", "days_in_status"]:
                    if key in raw and raw[key] is not None:
                        setattr(lead, key, raw[key])
                lead.stuck_score = stuck
                lead.priority = priority
                lead.last_scored_at = datetime.now(timezone.utc)
                lead.updated_at = datetime.now(timezone.utc)
                total_updated += 1
                source_updated += 1
            else:
                lead_data = {
                    "registry_source": source,
                    "external_id": raw["external_id"],
                    "project_name": raw.get("project_name", ""),
                    "project_developer": raw.get("project_developer"),
                    "developer_contact": raw.get("developer_contact"),
                    "developer_email": raw.get("developer_email"),
                    "country": raw.get("country"),
                    "region": raw.get("region"),
                    "methodology": raw.get("methodology"),
                    "sector": raw.get("sector"),
                    "status": raw.get("status", "unknown"),
                    "estimated_credits_per_year": raw.get("estimated_credits_per_year"),
                    "registry_url": raw.get("registry_url"),
                    "days_in_status": raw.get("days_in_status"),
                    "stuck_score": stuck,
                    "priority": priority,
                    "scraped_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                if raw.get("crediting_period_start"):
                    lead_data["crediting_period_start"] = dt_date.fromisoformat(raw["crediting_period_start"])
                if raw.get("crediting_period_end"):
                    lead_data["crediting_period_end"] = dt_date.fromisoformat(raw["crediting_period_end"])
                if raw.get("last_verification_date"):
                    lead_data["last_verification_date"] = dt_date.fromisoformat(raw["last_verification_date"])

                db.add(Lead(**lead_data))
                total_created += 1
                source_created += 1

        per_source.append({
            "source": source,
            "status": "error" if error_msg else ("live" if data_source == "live" else "demo"),
            "count": len(raw_leads),
            "created": source_created,
            "updated": source_updated,
            "error": error_msg,
            "data_source": data_source,
        })

        # Log this manual scrape run
        db.add(ScraperRun(
            source=source,
            scraped_at=datetime.now(timezone.utc),
            count=len(raw_leads),
            created=source_created,
            updated=source_updated,
            status="error" if error_msg else ("live" if data_source == "live" else "demo"),
            data_source=data_source,
            error_message=error_msg,
            mode="live" if any(s == "live" for s in [data_source]) else "demo",
        ))

    await db.commit()
    logger.info("scrape_completed", created=total_created, updated=total_updated, sources=sources, per_source=per_source)
    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.data_ingested,
        actor_id=current_user.id,
        target_type="lead",
        target_id=None,
        metadata={"event": "lead_scrape", "sources": sources},
    )
    return {
        "created": total_created,
        "updated": total_updated,
        "sources": sources,
        "per_source": per_source,
    }


@router.get("/stats/dashboard", response_model=LeadStats)
async def get_lead_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    # Total leads
    total_result = await db.execute(select(func.count(Lead.id)))
    total_leads = total_result.scalar() or 0

    # By registry
    by_registry = {}
    registry_result = await db.execute(
        select(Lead.registry_source, func.count(Lead.id)).group_by(Lead.registry_source)
    )
    for row in registry_result.all():
        by_registry[str(row[0])] = row[1]

    # By priority
    by_priority = {}
    priority_result = await db.execute(
        select(Lead.priority, func.count(Lead.id)).group_by(Lead.priority)
    )
    for row in priority_result.all():
        by_priority[str(row[0])] = row[1]

    # By country
    by_country = {}
    country_result = await db.execute(
        select(Lead.country, func.count(Lead.id)).group_by(Lead.country)
    )
    for row in country_result.all():
        by_country[str(row[0]) if row[0] else "Unknown"] = row[1]

    # By lead status
    by_lead_status = {}
    status_result = await db.execute(
        select(Lead.lead_status, func.count(Lead.id)).group_by(Lead.lead_status)
    )
    for row in status_result.all():
        by_lead_status[str(row[0])] = row[1]

    # Avg stuck score
    avg_result = await db.execute(select(func.avg(Lead.stuck_score)))
    avg_stuck_score = round(avg_result.scalar() or 0.0, 2)

    # High priority count (high + critical)
    hp_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.priority.in_(["high", "critical"]))
    )
    high_priority_count = hp_result.scalar() or 0

    # Critical count
    crit_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.priority == "critical")
    )
    critical_count = crit_result.scalar() or 0

    return LeadStats(
        total_leads=total_leads,
        by_registry=by_registry,
        by_priority=by_priority,
        by_country=by_country,
        by_lead_status=by_lead_status,
        avg_stuck_score=avg_stuck_score,
        high_priority_count=high_priority_count,
        critical_count=critical_count,
    )


@router.get("/health/scrapers")
async def get_scraper_health(
    _: User = Depends(require_viewer),
):
    """Return health status for all registry scrapers."""
    return health_check_all()


@router.post("/{lead_id}/convert-and-pre-audit", response_model=ProjectPreAuditOut, status_code=202)
async def convert_and_pre_audit_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    try:
        converter = LeadToProjectConverter(db)
        project = await converter.convert(lead)
    except LeadConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    runner = PreAuditRunner(db)
    pre_audit = await runner.run_for_project(project, lead_id=str(lead_id))

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_created,
        actor_id=current_user.id,
        target_type="project_pre_audit",
        target_id=pre_audit.id,
        metadata={"lead_id": str(lead_id), "project_id": str(project.id)},
    )
    return pre_audit
