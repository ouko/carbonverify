"""
Redis-backed session management for CarbonVerify.

Tracks user activity, enforces inactivity timeouts, and supports
multi-device session control.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import redis.asyncio as redis

from app.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Lazy connection
_redis_pool: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
            retry_on_timeout=True,
        )
    return _redis_pool


class SessionManager:
    """Manages user sessions in Redis."""

    SESSION_PREFIX = "session"
    USER_SESSIONS_PREFIX = "user_sessions"

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"{SessionManager.SESSION_PREFIX}:{session_id}"

    @staticmethod
    def _user_sessions_key(user_id: str) -> str:
        return f"{SessionManager.USER_SESSIONS_PREFIX}:{user_id}"

    @classmethod
    async def create_session(
        cls,
        user_id: str,
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Create a new session and return the session ID."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        session_data = {
            "user_id": user_id,
            "created_at": now.isoformat(),
            "last_activity_at": now.isoformat(),
            "device_fingerprint": device_fingerprint,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        r = _get_redis()
        pipe = r.pipeline()

        # Store session with TTL
        ttl = settings.SESSION_INACTIVITY_TIMEOUT_MINUTES * 60
        pipe.setex(cls._session_key(session_id), ttl, json.dumps(session_data))

        # Track session under user
        pipe.sadd(cls._user_sessions_key(user_id), session_id)

        await pipe.execute()
        logger.info("session_created", user_id=user_id, session_id=session_id)
        return session_id

    @classmethod
    async def get_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by ID."""
        r = _get_redis()
        data = await r.get(cls._session_key(session_id))
        if data:
            return json.loads(data)
        return None

    @classmethod
    async def update_activity(cls, session_id: str) -> bool:
        """Update last activity timestamp for a session."""
        r = _get_redis()
        data = await r.get(cls._session_key(session_id))
        if not data:
            return False

        session = json.loads(data)
        session["last_activity_at"] = datetime.now(timezone.utc).isoformat()

        ttl = settings.SESSION_INACTIVITY_TIMEOUT_MINUTES * 60
        await r.setex(cls._session_key(session_id), ttl, json.dumps(session))
        return True

    @classmethod
    async def destroy_session(cls, session_id: str) -> None:
        """Destroy a session."""
        r = _get_redis()
        data = await r.get(cls._session_key(session_id))
        if data:
            session = json.loads(data)
            user_id = session.get("user_id")
            if user_id:
                await r.srem(cls._user_sessions_key(user_id), session_id)
        await r.delete(cls._session_key(session_id))
        logger.info("session_destroyed", session_id=session_id)

    @classmethod
    async def destroy_all_user_sessions(cls, user_id: str, except_session: Optional[str] = None) -> int:
        """Destroy all sessions for a user, optionally keeping one."""
        r = _get_redis()
        session_ids = await r.smembers(cls._user_sessions_key(user_id))
        count = 0
        for sid in session_ids:
            if except_session and sid == except_session:
                continue
            await cls.destroy_session(sid)
            count += 1
        logger.info("sessions_destroyed_all", user_id=user_id, count=count)
        return count

    @classmethod
    async def is_session_valid(cls, session_id: str) -> bool:
        """Check if a session is still valid (exists and not expired)."""
        r = _get_redis()
        return await r.exists(cls._session_key(session_id)) == 1

    @classmethod
    async def list_user_sessions(cls, user_id: str) -> list[Dict[str, Any]]:
        """List all active sessions for a user."""
        r = _get_redis()
        session_ids = await r.smembers(cls._user_sessions_key(user_id))
        sessions = []
        for sid in session_ids:
            data = await r.get(cls._session_key(sid))
            if data:
                session = json.loads(data)
                session["session_id"] = sid
                sessions.append(session)
            else:
                # Clean up stale reference
                await r.srem(cls._user_sessions_key(user_id), sid)
        return sessions

    @classmethod
    async def list_all_sessions(cls) -> list[Dict[str, Any]]:
        """List all active sessions across all users."""
        r = _get_redis()
        sessions = []
        async for key in r.scan_iter(match=f"{cls.SESSION_PREFIX}:*"):
            data = await r.get(key)
            if data:
                session = json.loads(data)
                session["session_id"] = key.split(":", 1)[1]
                sessions.append(session)
        return sessions
