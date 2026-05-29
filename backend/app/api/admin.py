import asyncio
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
    # Total users + status breakdown
    total_coro = db.scalar(select(func.count(User.id)))
    active_coro = db.scalar(select(func.count(User.id)).where(User.is_active == True))
    inactive_coro = db.scalar(select(func.count(User.id)).where(User.is_active == False))
    locked_coro = db.scalar(
        select(func.count(User.id)).where(
            User.locked_until.isnot(None),
            User.locked_until > datetime.now(timezone.utc),
        )
    )
    total, active, inactive, locked = await asyncio.gather(
        total_coro, active_coro, inactive_coro, locked_coro
    )

    # By role — batch with asyncio.gather
    role_counts = {}
    role_coros = {
        role: db.scalar(select(func.count(User.id)).where(User.role == role))
        for role in ["admin", "operator", "developer", "viewer"]
    }
    role_results = await asyncio.gather(*role_coros.values())
    for role, count in zip(role_coros.keys(), role_results):
        role_counts[role] = count or 0

    # New users today / this week + MFA — batch with asyncio.gather
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    new_today_coro = db.scalar(select(func.count(User.id)).where(User.created_at >= today_start))
    new_week_coro = db.scalar(select(func.count(User.id)).where(User.created_at >= week_start))
    mfa_coro = db.scalar(select(func.count(User.id)).where(User.mfa_enabled == True))
    new_today, new_this_week, mfa_count = await asyncio.gather(
        new_today_coro, new_week_coro, mfa_coro
    )

    # Total active sessions (from Redis) — reuse pooled connection
    total_sessions = 0
    try:
        from app.auth.sessions import _get_redis
        r = _get_redis()
        async for _key in r.scan_iter(match="session:*"):
            total_sessions += 1
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
