from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timezone

from app.database import get_db
from app.config import get_settings
from app.schemas import HealthCheck
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=HealthCheck)
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    # Use the shared app-level limiter so rate-limit state and exception
    # handling are consistent with the rest of the application.
    limiter = getattr(request.app.state, "limiter", None)
    if limiter is not None:
        await limiter._check(request, "120/minute", "health")

    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "error"
        logger.error("health_db_error", error=str(e))

    try:
        from app.auth.sessions import _get_redis
        r = _get_redis()
        await r.ping()
    except Exception as e:
        redis_status = "error"
        logger.error("health_redis_error", error=str(e))

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return HealthCheck(
        status=overall,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.now(timezone.utc),
    )
