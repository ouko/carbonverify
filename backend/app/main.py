"""CarbonVerify FastAPI application entry point."""

from typing import Any

from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError, ValidationException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, REGISTRY
import prometheus_client
import logging

from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.request_id import RequestIDMiddleware
from app.core.client_ip import get_client_ip
from app.core import request_context
from app.database import engine
from app.auth.dependencies import get_current_user, require_admin
from app.security.siem_streaming import get_siem_streamer
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.projects import router as projects_router
from app.api.data_sources import router as data_sources_router
from app.api.calculations import router as calculations_router
from app.api.reports import router as reports_router
from app.api.review_queue import router as review_queue_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.websocket import router as websocket_router
from app.api.uploads import router as uploads_router
from app.api.webhooks import router as webhooks_router
from app.api.vvb_liaison import router as vvb_router
from app.api.orchestrator import router as orchestrator_router
from app.api.whatsapp import router as whatsapp_router
from app.api.audit import router as audit_router
from app.api.compliance import router as compliance_router
from app.api.brokerage import router as brokerage_router
from app.api.tokenization import router as tokenization_router
from app.api.corporate import router as corporate_router
from app.api.leads import router as leads_router
from app.api.validation_engine import router as validation_engine_router
from app.api.admin import router as admin_router
from app.api.api_keys import router as api_keys_router
from app.api.oauth import router as oauth_router

settings = get_settings()
logger = get_logger(__name__)


def _parse_trusted_proxies(raw: str) -> set[str]:
    """Parse a comma-separated list of trusted proxy IPs/CIDRs."""
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


TRUSTED_PROXIES = _parse_trusted_proxies(settings.TRUSTED_PROXIES)


def _proxy_aware_key_func(request: Request) -> str:
    """Rate-limit key that respects trusted reverse proxies."""
    return get_client_ip(request, TRUSTED_PROXIES)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    request_context.set_trusted_proxies(TRUSTED_PROXIES)
    logger.info("app_startup", environment=settings.ENVIRONMENT)
    siem = get_siem_streamer()
    await siem.start()
    try:
        yield
    finally:
        logger.info("app_shutdown")
        await siem.stop()
        await engine.dispose()


limiter = Limiter(key_func=_proxy_aware_key_func)

app = FastAPI(
    title="CarbonVerify API",
    description="Automated carbon credit MRV preparation platform",
    version="1.2.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestIDMiddleware)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # X-XSS-Protection removed — deprecated by OWASP, can enable XSS in some browsers
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # Content Security Policy
    csp = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    response.headers["Content-Security-Policy"] = csp
    return response


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    # Apply the limit to Content-Length; chunked uploads without a length header
    # are handled by server-level timeouts and streaming instead.
    content_length = request.headers.get("content-length")
    if content_length:
        max_size = 50 * 1024 * 1024 if request.url.path.startswith("/uploads") else 10 * 1024 * 1024
        try:
            length = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header"},
            )
        if length > max_size:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request entity too large"},
            )
    return await call_next(request)


# TrustedHostMiddleware — prevent Host header attacks
# Skip in test environment to avoid breaking test clients
if settings.ENVIRONMENT != "test":
    allowed_hosts = ["carbonverify.io", "*.carbonverify.io"]
    if settings.ENVIRONMENT == "development":
        allowed_hosts.extend(["localhost", "127.0.0.1"])
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts,
    )

# Production CORS: tighten in production, allow local dev
allow_origins = [settings.FRONTEND_URL] if settings.FRONTEND_URL else []
if settings.ENVIRONMENT == "development":
    allow_origins.extend([
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key", "X-Requested-With", "Accept", "Origin"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(data_sources_router)
app.include_router(calculations_router)
app.include_router(reports_router)
app.include_router(review_queue_router)
app.include_router(dashboard_router)
app.include_router(health_router)
app.include_router(websocket_router)
app.include_router(uploads_router)
app.include_router(webhooks_router)
app.include_router(vvb_router)
app.include_router(orchestrator_router)
app.include_router(whatsapp_router)
app.include_router(audit_router)
app.include_router(compliance_router)
app.include_router(brokerage_router)
app.include_router(tokenization_router)
app.include_router(corporate_router)
app.include_router(leads_router)
app.include_router(validation_engine_router)
app.include_router(admin_router)
app.include_router(api_keys_router)
app.include_router(oauth_router)


def _json_safe(value: Any) -> Any:
    """Recursively convert bytes and other non-JSON-serializable values."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_json_safe(v) for v in value)
    if isinstance(value, set):
        return sorted(_json_safe(v) for v in value)
    if isinstance(value, BaseModel):
        return value.model_dump()
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_errors = _json_safe(exc.errors())
    logger.warning(
        "request_validation_error",
        request_id=getattr(request.state, "request_id", None),
        errors=safe_errors,
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request", "errors": safe_errors},
    )


@app.exception_handler(ValidationException)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationException):
    safe_errors = _json_safe(exc.errors())
    logger.warning(
        "pydantic_validation_error",
        request_id=getattr(request.state, "request_id", None),
        errors=safe_errors,
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request", "errors": safe_errors},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "unhandled_exception",
        request_id=getattr(request.state, "request_id", None),
        path=str(request.url.path),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/metrics")
async def metrics(_: None = Depends(require_admin)):
    """Prometheus metrics endpoint — admin only."""
    return PlainTextResponse(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/")
@limiter.limit("60/minute")
async def root(request: Request):
    return {"message": "CarbonVerify API", "version": "1.2.0"}
