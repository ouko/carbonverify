from datetime import datetime, timedelta, timezone
from typing import Optional
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from app.core.encryption import compute_searchable_hash
from app.database import get_db
from app.models import User, RefreshToken, UserInvite, UserRoleEnum, AuditActionEnum
from app.schemas import Token, LoginRequest, RefreshRequest, UserCreate, UserOut, MFAVerifyRequest, PasswordChangeRequest, UserInviteCreate, UserInviteOut, InviteAcceptRequest
from app.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from app.auth.mfa import (
    generate_mfa_secret,
    verify_totp,
    generate_qr_code_png,
)
from app.auth.sessions import SessionManager
from app.auth.dependencies import validate_refresh_token, get_current_user, require_admin
from app.security.audit_logging import AuditLogger
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

MAX_FAILED_LOGINS = 5
LOCKOUT_DURATION_MINUTES = 30
REFRESH_COOKIE_NAME = "refresh_token"


def _get_login_email_key(request: Request) -> str:
    """Rate limit key based on login email address."""
    try:
        body = getattr(request, "_body", None)
        if body:
            data = json.loads(body)
            email = data.get("email")
            if email:
                return f"login:{email}"
    except Exception:
        pass
    return ""


def _get_mfa_temp_token_key(request: Request) -> str:
    """Rate limit key based on MFA temp token."""
    try:
        body = getattr(request, "_body", None)
        if body:
            data = json.loads(body)
            temp_token = data.get("temp_token")
            if temp_token:
                return f"mfa:{temp_token}"
    except Exception:
        pass
    return ""


def _get_device_fingerprint(request: Request) -> str:
    """Create a simple device fingerprint from request headers."""
    ua = request.headers.get("user-agent", "")
    accept = request.headers.get("accept", "")
    lang = request.headers.get("accept-language", "")
    return hash((ua, accept, lang))


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set refresh token as httpOnly cookie."""
    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
    )


@limiter.limit("5/minute")
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    email_hash = compute_searchable_hash(payload.email)
    result = await db.execute(select(User).where(User.email_hash == email_hash))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Self-registration defaults to viewer role for security
    # Only admins can create users with other roles via POST /users/
    user = User(
        email=payload.email,
        email_hash=email_hash,
        name=payload.name,
        role="viewer",
        mfa_enabled=False,
        hashed_password=get_password_hash(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_login,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "self_registration", "role": "viewer"},
    )

    logger.info("user_registered", user_id=str(user.id), email=user.email)
    return user


@limiter.limit("10/minute")
@limiter.limit("5/minute", key_func=_get_login_email_key)
@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1 of login: Validate credentials.

    If MFA is required and enabled, returns mfa_required=True with a temp token.
    Otherwise, returns full access token and sets refresh token as httpOnly cookie.
    """
    email_hash = compute_searchable_hash(payload.email)
    result = await db.execute(select(User).where(User.email_hash == email_hash))
    user = result.scalar_one_or_none()

    # Fallback: if no user found by email_hash, check for legacy users
    # with missing email_hash by querying with a single LIMIT to avoid
    # full table scans under load.
    if not user:
        logger.warning("login_email_hash_miss", email_hash=email_hash)
        legacy_result = await db.execute(
            select(User).where(
                and_(
                    User.email_hash.is_(None),
                    User.is_active == True,
                )
            ).limit(50)
        )
        for candidate in legacy_result.scalars().all():
            if candidate.email and candidate.email.lower() == payload.email.lower():
                user = candidate
                # Heal the missing hash so next login is fast
                user.email_hash = email_hash
                logger.info("login_fallback_match_healed", user_id=str(user.id))
                break

    audit = AuditLogger(db)

    # Check lockout BEFORE incrementing failed login count
    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        await audit.log_login(
            user_id=user.id,
            success=False,
            request=request,
        )
        raise HTTPException(
            status_code=403,
            detail=f"Account locked. Try again after {user.locked_until.isoformat()}",
        )

    if not user or not verify_password(payload.password, user.hashed_password):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                logger.warning("account_locked", user_id=str(user.id), failed_count=user.failed_login_count)
            await db.commit()
        await audit.log_login(
            user_id=user.id if user else None,
            success=False,
            request=request,
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Reset failed login count
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Check MFA requirement
    if user.mfa_enabled:
        # Issue temporary token valid for 5 minutes for MFA step
        temp_token = create_access_token(
            str(user.id),
            expires_delta=timedelta(minutes=5),
        )
        logger.info("login_mfa_required", user_id=str(user.id))
        return {
            "mfa_required": True,
            "temp_token": temp_token,
            "message": "Please provide TOTP code",
        }

    # No MFA required - issue full tokens
    return await _issue_tokens(user, request, response, db)


@limiter.limit("10/minute")
@limiter.limit("5/minute", key_func=_get_mfa_temp_token_key)
@router.post("/mfa/verify")
async def verify_mfa(
    payload: MFAVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2 of MFA login: Verify TOTP code.
    """
    payload_dict = decode_token(payload.temp_token)
    if not payload_dict or payload_dict.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired temp token")

    user_id = payload_dict.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account deactivated")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Account locked")

    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not configured for this user")

    if not verify_totp(user.mfa_secret, payload.totp_code):
        audit = AuditLogger(db)
        await audit.log_login(user_id=user.id, success=False, request=request, mfa_used=True)
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    return await _issue_tokens(user, request, response, db, mfa_used=True, mfa_verified=True)


@limiter.limit("5/minute")
@router.post("/mfa/setup")
async def setup_mfa(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate MFA secret and QR code for the current user.
    Must be confirmed with /mfa/confirm before being enabled.
    """
    secret = generate_mfa_secret()

    # Store temporarily in metadata (not enabled until confirmed)
    # In production, you might use a separate pending_mfa_secret column
    qr_code = generate_qr_code_png(secret, current_user.email)

    return {
        "secret": secret,
        "qr_code": qr_code,
        "message": "Scan QR code with authenticator app, then POST /mfa/confirm with a code",
    }


class MFAConfirmRequest(BaseModel):
    secret: str
    totp_code: str
    current_password: str


@limiter.limit("10/minute")
@router.post("/mfa/confirm", response_model=UserOut)
async def confirm_mfa(
    payload: MFAConfirmRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm MFA setup with secret and verification code."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if not verify_totp(payload.secret, payload.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    current_user.mfa_secret = payload.secret
    current_user.mfa_enabled = True
    await db.commit()
    await db.refresh(current_user)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.mfa_enabled,
        actor_id=current_user.id,
        target_type="user",
        target_id=current_user.id,
    )

    logger.info("mfa_enabled", user_id=str(current_user.id))
    return current_user


@limiter.limit("5/minute")
@router.post("/mfa/disable")
async def disable_mfa(
    request: Request,
    current_user: User = Depends(require_admin),
    target_user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Disable MFA for a user (admin only, or self)."""
    result = await db.execute(select(User).where(User.id == (target_user_id or current_user.id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.mfa_enabled = False
    user.mfa_secret = None
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.mfa_disabled,
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
    )

    logger.info("mfa_disabled", admin_id=str(current_user.id), target_user_id=str(user.id))
    return {"message": "MFA disabled"}


@limiter.limit("20/minute")
@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate refresh tokens.

    Reads refresh token from httpOnly cookie, validates it, revokes it, and issues a new pair.
    """
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    user, old_token_record = await validate_refresh_token(refresh_token, db)

    # Revoke old token
    old_token_record.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_login,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "token_refresh"},
    )

    # Issue new tokens
    old_session_id = request.headers.get("x-session-id")
    mfa_verified = False
    if old_session_id:
        old_session = await SessionManager.get_session(old_session_id)
        if old_session:
            mfa_verified = old_session.get("mfa_verified", False)

    return await _issue_tokens(user, request, response, db, is_refresh=True, mfa_verified=mfa_verified)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout user and destroy session."""
    session_id = request.headers.get("x-session-id")
    if session_id:
        await SessionManager.destroy_session(session_id)

    # Revoke the refresh token from the cookie
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        token_hash = hash_token(refresh_token)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()

    # Clear refresh token cookie
    _clear_refresh_cookie(response)

    audit = AuditLogger(db)
    await audit.log_logout(user_id=current_user.id, request=request)

    logger.info("user_logout", user_id=str(current_user.id))
    return {"message": "Logged out successfully"}


@router.post("/logout-all")
async def logout_all_sessions(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout from all devices."""
    session_id = request.headers.get("x-session-id")
    await SessionManager.destroy_all_user_sessions(str(current_user.id), except_session=session_id)

    # Also revoke all refresh tokens
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()

    # Clear refresh token cookie
    _clear_refresh_cookie(response)

    audit = AuditLogger(db)
    await audit.log_logout(user_id=current_user.id, request=request)

    logger.info("user_logout_all", user_id=str(current_user.id))
    return {"message": "All sessions terminated"}


@router.get("/sessions")
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """List all active sessions for the current user."""
    sessions = await SessionManager.list_user_sessions(str(current_user.id))
    current_session_id = request.headers.get("x-session-id")
    result = []
    for s in sessions:
        result.append({
            "id": s["session_id"],
            "device": s.get("user_agent", "Unknown device"),
            "ip": s.get("ip_address", "unknown"),
            "last_active": s.get("last_activity_at", s.get("created_at")),
            "created_at": s.get("created_at"),
            "current": s["session_id"] == current_session_id,
        })
    return result


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific session. Users can only revoke their own sessions."""
    session = await SessionManager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(session.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Cannot revoke another user's session")

    await SessionManager.destroy_session(session_id)

    # Revoke all refresh tokens for this user as defense
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_logout,
        actor_id=current_user.id,
        target_type="user",
        target_id=current_user.id,
        metadata={"event": "session_revoked", "session_id": session_id},
    )

    logger.info("session_revoked", session_id=session_id, user_id=str(current_user.id))
    return {"message": "Session revoked"}


@limiter.limit("10/minute")
@router.post("/change-password")
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    current_user.hashed_password = get_password_hash(payload.new_password)
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="user",
        target_id=current_user.id,
        metadata={"event": "password_change"},
    )

    logger.info("password_changed", user_id=str(current_user.id))
    return {"message": "Password updated successfully"}


@limiter.limit("10/minute")
@router.post("/admin/invite", response_model=UserInviteOut, status_code=status.HTTP_201_CREATED)
async def invite_user(
    payload: UserInviteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin-only: generate an invite token for a new user."""
    email_hash = compute_searchable_hash(payload.email)

    # Check if email already exists
    result = await db.execute(select(User).where(User.email_hash == email_hash))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check for existing active invite
    result = await db.execute(
        select(UserInvite).where(
            UserInvite.email_hash == email_hash,
            UserInvite.used_at.is_(None),
            UserInvite.expires_at > datetime.now(timezone.utc),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Active invite already exists for this email")

    token = secrets.token_urlsafe(32)
    invite = UserInvite(
        token=token,
        email=payload.email,
        email_hash=email_hash,
        name=payload.name,
        role=UserRoleEnum(payload.role),
        permissions={"granted": payload.permissions, "revoked": []},
        invited_by=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_created,
        actor_id=current_user.id,
        target_type="user_invite",
        target_id=invite.id,
        metadata={"email": payload.email, "role": payload.role, "token": token},
    )

    logger.info("invite_created", invite_id=str(invite.id), email=payload.email, admin_id=str(current_user.id))
    return invite


@limiter.limit("10/minute")
@router.post("/invite/accept", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def accept_invite(
    payload: InviteAcceptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Accept an invite token and create a user account."""
    async with db.begin():
        result = await db.execute(
            select(UserInvite).where(
                UserInvite.token == payload.token,
                UserInvite.used_at.is_(None),
                UserInvite.expires_at > datetime.now(timezone.utc),
            ).with_for_update()
        )
        invite = result.scalar_one_or_none()
        if not invite:
            raise HTTPException(status_code=400, detail="Invalid or expired invite token")

        # Create user from invite (allow name override from payload)
        user = User(
            email=invite.email,
            email_hash=invite.email_hash,
            name=payload.name.strip() if payload.name else invite.name,
            role=invite.role,
            hashed_password=get_password_hash(payload.password),
            permissions=invite.permissions,
            is_active=True,
        )
        db.add(user)
        await db.flush()

        # Mark invite as used
        invite.used_at = datetime.now(timezone.utc)
        invite.used_by_user_id = user.id

    await db.refresh(user)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_created,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "invite_accepted", "invite_id": str(invite.id)},
    )

    logger.info("invite_accepted", user_id=str(user.id), invite_id=str(invite.id))
    return user


async def _issue_tokens(
    user: User,
    request: Request,
    response: Response,
    db: AsyncSession,
    mfa_used: bool = False,
    is_refresh: bool = False,
    mfa_verified: bool = False,
) -> Token:
    """Issue access and refresh tokens, create session and refresh token record."""
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    # Store refresh token hash
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        device_fingerprint=str(_get_device_fingerprint(request)),
        ip_address=_get_client_ip(request),
    )
    db.add(token_record)

    # Create session
    session_id = await SessionManager.create_session(
        user_id=str(user.id),
        device_fingerprint=str(_get_device_fingerprint(request)),
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        extra_data={"mfa_verified": mfa_verified},
    )

    await db.commit()

    # Set refresh token as httpOnly cookie
    _set_refresh_cookie(response, refresh_token)

    audit = AuditLogger(db)
    await audit.log_login(user_id=user.id, success=True, request=request, mfa_used=mfa_used)

    logger.info("tokens_issued", user_id=str(user.id), is_refresh=is_refresh)
    return Token(
        access_token=access_token,
        token_type="bearer",  # nosec B106 — OAuth2 standard token type
        session_id=session_id,
    )
