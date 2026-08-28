import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from jose import JWTError, jwt

from app.config import get_settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def create_applicant_token(application_id: uuid.UUID, expires_days: int = TOKEN_EXPIRE_DAYS) -> str:
    """Create a time-limited JWT for public applicant access."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=expires_days)
    payload = {
        "sub": str(application_id),
        "type": "applicant",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_applicant_token(token: str) -> Optional[uuid.UUID]:
    """Verify an applicant token and return the application_id, or None."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "applicant":
            return None
        app_id = uuid.UUID(payload.get("sub"))
        return app_id
    except (JWTError, ValueError, TypeError):
        return None
