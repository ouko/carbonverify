from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from app.models import User, RefreshToken
from app.schemas import Token, LoginRequest, RefreshRequest, UserCreate, UserOut, MFAVerifyRequest
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
    is_mfa_required,
)
from app.auth.sessions import SessionManager
from app.auth.dependencies import validate_refresh_token
from app.security.audit_logging import AuditLogger
from app.core.logging import get_logger

logger = get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED_LOGINS = 5
LOCKOUT_DURATION_MINUTES = 30


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


@limiter.limit("5/minute")
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == payload.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        name=payload.name,
        role=payload.role,
        mfa_enabled=payload.mfa_enabled,
        hashed_password=get_password_hash(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    audit = AuditLogger(db)
    await audit.log(
        action_type=__import__("app.models", fromlist=["AuditActionEnum"]).AuditActionEnum.user_login,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "registration"},
    )

    logger.info("user_registered", user_id=str(user.id), email=user.email)
    return user


@limiter.limit("10/minute")
@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1 of login: Validate credentials.

    If MFA is required and enabled, returns mfa_required=True with a temp token.
    Otherwise, returns full access + refresh tokens.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    audit = AuditLogger(db)

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

    # Check lockout
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=403,
            detail=f"Account locked. Try again after {user.locked_until.isoformat()}",
        )

    # Reset failed login count
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Check MFA requirement
    if user.mfa_enabled and is_mfa_required(user.role.value):
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
    return await _issue_tokens(user, request, db)


@router.post("/mfa/verify")
async def verify_mfa(
    payload: MFAVerifyRequest,
    request: Request,
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

    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not configured for this user")

    if not verify_totp(user.mfa_secret, payload.totp_code):
        audit = AuditLogger(db)
        await audit.log_login(user_id=user.id, success=False, request=request, mfa_used=True)
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    return await _issue_tokens(user, request, db, mfa_used=True)


@router.post("/mfa/setup")
async def setup_mfa(
    current_user: User = Depends(__import__("app.auth.dependencies", fromlist=["get_current_user"]).get_current_user),
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


@router.post("/mfa/confirm")
async def confirm_mfa(
    payload: MFAVerifyRequest,
    current_user: User = Depends(__import__("app.auth.dependencies", fromlist=["get_current_user"]).get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm MFA setup by verifying a TOTP code generated from the secret."""
    # The secret is passed in the totp_code field for confirmation
    # Actually, we need to receive the secret separately. Let me adjust.
    # For now, require the user to pass the secret they received from setup
    raise HTTPException(status_code=501, detail="Use /mfa/setup and provide secret in confirm payload")


class MFAConfirmRequest(LoginRequest):
    secret: str
    totp_code: str


@router.post("/mfa/confirm", response_model=UserOut)
async def confirm_mfa_v2(
    payload: MFAConfirmRequest,
    current_user: User = Depends(__import__("app.auth.dependencies", fromlist=["get_current_user"]).get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm MFA setup with secret and verification code."""
    if not verify_totp(payload.secret, payload.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    current_user.mfa_secret = payload.secret
    current_user.mfa_enabled = True
    await db.commit()
    await db.refresh(current_user)

    audit = AuditLogger(db)
    await audit.log(
        action_type=__import__("app.models", fromlist=["AuditActionEnum"]).AuditActionEnum.mfa_enabled,
        actor_id=current_user.id,
        target_type="user",
        target_id=current_user.id,
    )

    logger.info("mfa_enabled", user_id=str(current_user.id))
    return current_user


@router.post("/mfa/disable")
async def disable_mfa(
    current_user: User = Depends(__import__("app.auth.dependencies", fromlist=["require_admin"]).require_admin),
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
        action_type=__import__("app.models", fromlist=["AuditActionEnum"]).AuditActionEnum.mfa_disabled,
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
    )

    logger.info("mfa_disabled", admin_id=str(current_user.id), target_user_id=str(user.id))
    return {"message": "MFA disabled"}


@limiter.limit("20/minute")
@router.post("/refresh", response_model=Token)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate refresh tokens.

    Validates the old refresh token, revokes it, and issues a new pair.
    """
    user, old_token_record = await validate_refresh_token(payload.refresh_token, db)

    # Revoke old token
    old_token_record.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    # Issue new tokens
    return await _issue_tokens(user, request, db, is_refresh=True)


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(__import__("app.auth.dependencies", fromlist=["get_current_user"]).get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout user and destroy session."""
    session_id = request.headers.get("x-session-id")
    if session_id:
        await SessionManager.destroy_session(session_id)

    audit = AuditLogger(db)
    await audit.log_logout(user_id=current_user.id, request=request)

    logger.info("user_logout", user_id=str(current_user.id))
    return {"message": "Logged out successfully"}


@router.post("/logout-all")
async def logout_all_sessions(
    request: Request,
    current_user: User = Depends(__import__("app.auth.dependencies", fromlist=["get_current_user"]).get_current_user),
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

    audit = AuditLogger(db)
    await audit.log_logout(user_id=current_user.id, request=request)

    logger.info("user_logout_all", user_id=str(current_user.id))
    return {"message": "All sessions terminated"}


async def _issue_tokens(
    user: User,
    request: Request,
    db: AsyncSession,
    mfa_used: bool = False,
    is_refresh: bool = False,
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
    )

    await db.commit()

    audit = AuditLogger(db)
    await audit.log_login(user_id=user.id, success=True, request=request, mfa_used=mfa_used)

    logger.info("tokens_issued", user_id=str(user.id), is_refresh=is_refresh)
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",  # nosec B106 — OAuth2 standard token type
        session_id=session_id,
    )
