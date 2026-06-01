"""API key authentication for machine-to-machine access."""

import hashlib
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import ApiKey, User
from app.core.logging import get_logger

logger = get_logger(__name__)


async def validate_api_key(raw_key: str, db: AsyncSession) -> ApiKey:
    """Validate an API key and return the key record with associated user."""
    if not raw_key.startswith("cv_") or len(raw_key) < 10:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active == True,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key expired",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("api_key_used", key_id=str(api_key.id), prefix=api_key.key_prefix)
    return api_key


async def get_user_from_api_key(api_key: ApiKey, db: AsyncSession) -> User:
    """Get the user associated with an API key."""
    result = await db.execute(select(User).where(User.id == api_key.created_by))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner account is inactive",
        )
    return user
