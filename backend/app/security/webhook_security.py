"""Webhook security utilities: replay protection and HMAC validation."""

import hashlib
import hmac
import time
from typing import Optional

import redis.asyncio as redis

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_redis_pool: Optional[redis.Redis] = None

REPLAY_WINDOW_SECONDS = 300  # 5 minutes


def _get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_pool


async def check_replay_protection(
    identifier: str,
    ttl_seconds: int = REPLAY_WINDOW_SECONDS,
) -> bool:
    """
    Check if an identifier has been seen recently (replay protection).

    Returns True if the request is fresh (not a replay), False if it's a replay.
    """
    try:
        r = _get_redis()
        key = f"webhook:replay:{identifier}"
        # SET NX EX atomically sets the key only if it doesn't exist
        result = await r.set(key, "1", nx=True, ex=ttl_seconds)
        return result is not None  # True if key was set (fresh), False if already existed
    except Exception as exc:
        logger.error("replay_protection_error", error=str(exc))
        # Fail open if Redis is unavailable — better to accept a potential replay
        # than to drop legitimate webhooks
        return True


def compute_hmac_signature(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 hex signature for a payload."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_hmac_signature(payload: bytes, secret: str, signature: str) -> bool:
    """Verify HMAC-SHA256 hex signature for a payload."""
    expected = compute_hmac_signature(payload, secret)
    return hmac.compare_digest(expected, signature)


def build_request_identifier(
    signature: str,
    timestamp: Optional[int] = None,
) -> str:
    """Build a replay-protection identifier from a signature and optional timestamp."""
    if timestamp is not None:
        # Bucket timestamps to 1-minute windows to allow slight clock skew
        bucket = timestamp // 60
        return hashlib.sha256(f"{signature}:{bucket}".encode()).hexdigest()
    return hashlib.sha256(signature.encode()).hexdigest()
