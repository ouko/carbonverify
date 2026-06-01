"""OAuth 2.0 / SSO endpoints for Google, Microsoft, and Okta."""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models import User, OAuthAccount, AuditActionEnum, UserRoleEnum
from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, create_refresh_token, hash_token
from app.auth.sessions import SessionManager
from app.security.audit_logging import AuditLogger
from app.config import get_settings
from app.core.encryption import compute_searchable_hash
from app.core.logging import get_logger
from app.api.auth import _set_refresh_cookie, _get_device_fingerprint, _get_client_ip

logger = get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth/oauth", tags=["oauth"])
settings = get_settings()

# Provider configurations
_OAUTH_PROVIDERS = {
    "google": {
        "client_id": settings.OAUTH_GOOGLE_CLIENT_ID,
        "client_secret": settings.OAUTH_GOOGLE_CLIENT_SECRET,
        "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
        "scope": "openid email profile",
    },
    "microsoft": {
        "client_id": settings.OAUTH_MICROSOFT_CLIENT_ID,
        "client_secret": settings.OAUTH_MICROSOFT_CLIENT_SECRET,
        "server_metadata_url": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
        "scope": "openid email profile",
    },
    "okta": {
        "client_id": settings.OAUTH_OKTA_CLIENT_ID,
        "client_secret": settings.OAUTH_OKTA_CLIENT_SECRET,
        "server_metadata_url": f"{settings.OAUTH_OKTA_DOMAIN}/.well-known/openid-configuration" if settings.OAUTH_OKTA_DOMAIN else "",
        "scope": "openid email profile",
    },
}


def _get_oauth_client(provider: str):
    """Get an AsyncOAuth2Client for the specified provider."""
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    config = _OAUTH_PROVIDERS.get(provider)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unknown OAuth provider: {provider}")

    if not config["client_id"]:
        raise HTTPException(status_code=400, detail=f"OAuth provider {provider} is not configured")

    return AsyncOAuth2Client(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        server_metadata_url=config["server_metadata_url"],
        scope=config["scope"],
    )


@limiter.limit("60/minute")
@router.get("/accounts")
async def list_oauth_accounts(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List OAuth accounts linked to the current user."""
    result = await db.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "provider": a.provider,
            "provider_account_id": a.provider_account_id,
            "created_at": a.created_at.isoformat(),
        }
        for a in accounts
    ]


@limiter.limit("10/minute")
@router.get("/{provider}")
async def oauth_login(
    provider: str,
    request: Request,
):
    """Initiate OAuth login flow. Returns the authorization URL to redirect the user."""
    client = _get_oauth_client(provider)
    redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/oauth/{provider}/callback"

    authorization_url, state = client.create_authorization_url(
        client.server_metadata["authorization_endpoint"],
        redirect_uri=redirect_uri,
    )

    # Store state in a short-lived cookie for CSRF protection
    response = Response()
    response.set_cookie(
        key=f"oauth_state_{provider}",
        value=state,
        max_age=600,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )
    response.headers["location"] = authorization_url
    response.status_code = status.HTTP_307_TEMPORARY_REDIRECT
    return response


@limiter.limit("20/minute")
@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    response: Response,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback, create or link user, issue tokens."""
    client = _get_oauth_client(provider)

    # Verify state to prevent CSRF
    expected_state = request.cookies.get(f"oauth_state_{provider}")
    if not expected_state or expected_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/oauth/{provider}/callback"

    # Exchange code for token
    try:
        token = await client.fetch_token(
            client.server_metadata["token_endpoint"],
            authorization_response=str(request.url),
            redirect_uri=redirect_uri,
        )
    except Exception as e:
        logger.error("oauth_token_fetch_failed", provider=provider, error=str(e))
        raise HTTPException(status_code=400, detail="OAuth token exchange failed")

    # Fetch user info from ID token or userinfo endpoint
    try:
        id_token = token.get("id_token")
        if id_token and "id_token_signed_response_alg" in client.server_metadata:
            user_info = client.parse_id_token(token)
        else:
            resp = await client.get(client.server_metadata["userinfo_endpoint"])
            resp.raise_for_status()
            user_info = resp.json()
    except Exception as e:
        logger.error("oauth_userinfo_failed", provider=provider, error=str(e))
        raise HTTPException(status_code=400, detail="Failed to fetch user info")

    email = user_info.get("email", "").lower()
    name = user_info.get("name", email.split("@")[0])
    provider_account_id = str(user_info.get("sub", user_info.get("id", "")))

    if not email:
        raise HTTPException(status_code=400, detail="OAuth provider did not return email")

    # Check for existing OAuth account
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_account_id == provider_account_id,
        )
    )
    oauth_account = result.scalar_one_or_none()

    if oauth_account:
        # Existing linked account — log in
        result = await db.execute(select(User).where(User.id == oauth_account.user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail="Account is deactivated")

        # Update tokens
        oauth_account.access_token = token.get("access_token")
        oauth_account.refresh_token = token.get("refresh_token")
        expires_in = token.get("expires_in")
        if expires_in:
            oauth_account.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        await db.commit()

        audit = AuditLogger(db)
        await audit.log_login(user_id=user.id, success=True, request=request)
        logger.info("oauth_login", provider=provider, user_id=str(user.id))

        return await _issue_oauth_tokens(user, request, response, db)

    # Check if user exists by email
    email_hash = compute_searchable_hash(email)
    result = await db.execute(select(User).where(User.email_hash == email_hash))
    user = result.scalar_one_or_none()

    if user:
        # Link OAuth to existing user
        oauth = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_account_id=provider_account_id,
            access_token=token.get("access_token"),
            refresh_token=token.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=token.get("expires_in", 3600)) if token.get("expires_in") else None,
        )
        db.add(oauth)
        await db.commit()

        audit = AuditLogger(db)
        await audit.log_login(user_id=user.id, success=True, request=request)
        logger.info("oauth_linked_existing", provider=provider, user_id=str(user.id))

        return await _issue_oauth_tokens(user, request, response, db)

    # Create new user
    user = User(
        email=email,
        email_hash=email_hash,
        name=name,
        role=UserRoleEnum.viewer,
        hashed_password="",  # No password for OAuth-only users
        is_active=True,
    )
    db.add(user)
    await db.flush()

    oauth = OAuthAccount(
        user_id=user.id,
        provider=provider,
        provider_account_id=provider_account_id,
        access_token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=token.get("expires_in", 3600)) if token.get("expires_in") else None,
    )
    db.add(oauth)
    await db.commit()
    await db.refresh(user)

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_created,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        metadata={"event": "oauth_registration", "provider": provider},
    )
    logger.info("oauth_new_user", provider=provider, user_id=str(user.id))

    return await _issue_oauth_tokens(user, request, response, db)


@limiter.limit("10/minute")
@router.post("/{provider}/link")
async def link_oauth_account(
    provider: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Link an OAuth provider to the current user (initiates flow)."""
    client = _get_oauth_client(provider)
    redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/oauth/{provider}/callback"

    authorization_url, state = client.create_authorization_url(
        client.server_metadata["authorization_endpoint"],
        redirect_uri=redirect_uri,
        state=f"link:{current_user.id}",
    )

    response = Response()
    response.set_cookie(
        key=f"oauth_state_{provider}",
        value=state,
        max_age=600,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )
    return {"authorization_url": authorization_url}


@limiter.limit("10/minute")
@router.delete("/{provider}/unlink")
async def unlink_oauth_account(
    provider: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unlink an OAuth provider from the current user."""
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == current_user.id,
            OAuthAccount.provider == provider,
        )
    )
    oauth_account = result.scalar_one_or_none()
    if not oauth_account:
        raise HTTPException(status_code=404, detail="OAuth account not linked")

    # Prevent unlinking if user has no password set
    if not current_user.hashed_password:
        raise HTTPException(status_code=400, detail="Set a password before unlinking your only login method")

    await db.delete(oauth_account)
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        action_type=AuditActionEnum.user_updated,
        actor_id=current_user.id,
        target_type="oauth_account",
        target_id=oauth_account.id,
        metadata={"event": "unlinked", "provider": provider},
    )

    logger.info("oauth_unlinked", provider=provider, user_id=str(current_user.id))
    return {"message": f"{provider} account unlinked"}


async def _issue_oauth_tokens(
    user: User,
    request: Request,
    response: Response,
    db: AsyncSession,
):
    """Issue tokens after OAuth authentication."""
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    from app.models import RefreshToken
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        device_fingerprint=str(_get_device_fingerprint(request)),
        ip_address=_get_client_ip(request),
    )
    db.add(token_record)

    session_id = await SessionManager.create_session(
        user_id=str(user.id),
        device_fingerprint=str(_get_device_fingerprint(request)),
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    await db.commit()
    _set_refresh_cookie(response, refresh_token)

    logger.info("oauth_tokens_issued", user_id=str(user.id))
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "session_id": session_id,
    }
