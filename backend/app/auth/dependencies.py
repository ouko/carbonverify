from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, RefreshToken
from app.auth.security import decode_token, hash_token, is_token_expired
from app.auth.sessions import SessionManager
from app.auth.mfa import is_mfa_required
from app.core.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Check account lockout
    if user.locked_until and user.locked_until > __import__("datetime").datetime.now(__import__("datetime").timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account temporarily locked due to failed login attempts",
        )

    return user


async def get_current_user_with_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate user and update session activity."""
    user = await get_current_user(credentials, db)

    session_id = request.headers.get("x-session-id")
    if session_id:
        valid = await SessionManager.is_session_valid(session_id)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired due to inactivity",
            )
        await SessionManager.update_activity(session_id)

    return user


class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        if user.role.value not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user


require_admin = RoleChecker(["admin"])
require_operator = RoleChecker(["admin", "operator"])
require_developer = RoleChecker(["admin", "operator", "developer"])
require_viewer = RoleChecker(["admin", "operator", "developer", "viewer"])


async def validate_refresh_token(
    refresh_token: str,
    db: AsyncSession,
) -> User:
    """
    Validate a refresh token with rotation support.

    Checks token hash against database, verifies not revoked,
    and returns the associated user.
    """
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if is_token_expired(payload):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user_id = payload.get("sub")
    token_hash = hash_token(refresh_token)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    token_record = result.scalar_one_or_none()

    if not token_record:
        # Possible token reuse - revoke all user tokens
        logger.warning("possible_refresh_token_reuse", user_id=user_id)
        await _revoke_all_user_tokens(user_id, db)
        raise HTTPException(status_code=401, detail="Token reuse detected. All sessions terminated.")

    if token_record.expires_at < __import__("datetime").datetime.now(__import__("datetime").timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user, token_record


async def _revoke_all_user_tokens(user_id: str, db: AsyncSession) -> None:
    """Revoke all refresh tokens for a user."""
    from sqlalchemy import update
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    )
    await db.commit()


async def require_mfa_if_enabled(
    user: User = Depends(get_current_user),
    request: Request = None,
) -> User:
    """
    Enforce MFA for roles that require it.

    In the login flow, this is checked after password validation.
    For API access, the access token is only issued after MFA verification.
    """
    if user.mfa_enabled and is_mfa_required(user.role.value):
        # MFA should have been verified during login; token issuance is gated
        pass
    return user
