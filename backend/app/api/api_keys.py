"""API key management endpoints."""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import ApiKey, User, AuditActionEnum
from app.schemas import ApiKeyCreateRequest, ApiKeyOut, ApiKeyCreateResponse
from app.auth.dependencies import get_current_user, require_permission
from app.auth.api_key_auth import validate_api_key
from app.security.audit_logging import AuditLogger
from app.permissions import list_all_permissions
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api-keys", tags=["api_keys"])

API_KEY_PREFIX = "cv_"


@router.post("/", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system:configure")),
):
    """Create a new API key. The full key is returned once and never again."""
    # Validate scopes
    all_perms = set(list_all_permissions())
    invalid_scopes = [s for s in payload.scopes if s not in all_perms]
    if invalid_scopes:
        raise HTTPException(status_code=400, detail=f"Invalid scopes: {invalid_scopes}")

    # Validate that creator has all requested scopes (can't grant what you don't have)
    from app.permissions import has_permission
    for scope in payload.scopes:
        if not has_permission(current_user.role.value, current_user.permissions or [], scope):
            raise HTTPException(
                status_code=403,
                detail=f"Cannot grant scope '{scope}' — you do not possess it",
            )

    raw_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]

    api_key = ApiKey(
        name=payload.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=payload.scopes,
        created_by=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days) if payload.expires_in_days else None,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_created,
        actor_id=current_user.id,
        target_type="api_key",
        target_id=api_key.id,
        metadata={"name": payload.name, "scopes": payload.scopes},
    )

    logger.info("api_key_created", key_id=str(api_key.id), prefix=key_prefix, user_id=str(current_user.id))
    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_prefix=key_prefix,
        scopes=api_key.scopes,
        created_by=api_key.created_by,
        expires_at=api_key.expires_at,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
    )


@router.get("/", response_model=List[ApiKeyOut])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system:configure")),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List all API keys (full keys are never returned)."""
    result = await db.execute(
        select(ApiKey)
        .order_by(ApiKey.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system:configure")),
):
    """Revoke an API key."""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="api_key",
        target_id=api_key.id,
        metadata={"event": "revoked"},
    )

    logger.info("api_key_revoked", key_id=str(api_key.id), user_id=str(current_user.id))
    return None
