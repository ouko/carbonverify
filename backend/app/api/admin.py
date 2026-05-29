from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models import User
from app.schemas import AdminStats
from app.auth.dependencies import require_permission
from app.auth.sessions import SessionManager
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/sessions")
async def list_all_sessions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("users:manage_permissions")),
):
    """List all active sessions across the platform."""
    sessions = await SessionManager.list_all_sessions()

    # Look up user names/emails for all sessions
    user_ids = list({s.get("user_id") for s in sessions if s.get("user_id")})
    users = {}
    if user_ids:
        result = await db.execute(select(User.id, User.name, User.email).where(User.id.in_(user_ids)))
        for row in result:
            users[str(row.id)] = {"name": row.name, "email": row.email}

    return [
        {
            "id": s.get("session_id"),
            "user_id": s.get("user_id"),
            "user_name": users.get(s.get("user_id", ""), {}).get("name", "Unknown"),
            "user_email": users.get(s.get("user_id", ""), {}).get("email", ""),
            "device": s.get("user_agent", "Unknown"),
            "ip": s.get("ip_address", "Unknown"),
            "last_active": s.get("last_activity_at"),
            "created_at": s.get("created_at"),
            "current": False,
        }
        for s in sessions
    ]


@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("system:view_stats")),
):
    """Get system-wide admin statistics."""
    # Total users
    total = await db.scalar(select(func.count(User.id)))

    # Active / inactive / locked
    active = await db.scalar(select(func.count(User.id)).where(User.is_active == True))
    inactive = await db.scalar(select(func.count(User.id)).where(User.is_active == False))
    locked = await db.scalar(
        select(func.count(User.id)).where(
            User.locked_until.isnot(None),
            User.locked_until > datetime.now(timezone.utc),
        )
    )

    # By role
    role_counts = {}
    for role in ["admin", "operator", "developer", "viewer"]:
        count = await db.scalar(select(func.count(User.id)).where(User.role == role))
        role_counts[role] = count or 0

    # New users today / this week
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    new_today = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )
    new_this_week = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= week_start)
    )

    # MFA enabled count
    mfa_count = await db.scalar(select(func.count(User.id)).where(User.mfa_enabled == True))

    # Total active sessions (from Redis)
    # This is approximate — we scan Redis for session keys
    total_sessions = 0
    try:
        import redis.asyncio as aioredis
        from app.config import get_settings
        settings = get_settings()
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        async for key in r.scan_iter(match="session:*"):
            total_sessions += 1
        await r.aclose()
    except Exception as e:
        logger.warning("failed_to_count_sessions", error=str(e))

    return AdminStats(
        total_users=total or 0,
        active_users=active or 0,
        inactive_users=inactive or 0,
        locked_users=locked or 0,
        users_by_role=role_counts,
        new_users_today=new_today or 0,
        new_users_this_week=new_this_week or 0,
        total_sessions=total_sessions,
        mfa_enabled_count=mfa_count or 0,
    )


@router.get("/permissions")
async def list_permissions(
    _: User = Depends(require_permission("users:manage_permissions")),
):
    """List all available permissions."""
    from app.permissions import list_all_permissions
    return {"permissions": list_all_permissions()}
