import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt
from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def verify_and_update_password(plain_password: str, hashed_password: str) -> tuple[bool, Optional[str]]:
    """Verify password and return a new hash if the cost rounds differ from config."""
    return pwd_context.verify_and_update(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "type": "access", "iat": datetime.now(timezone.utc)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode a JWT, trying current and previous secret keys for rotation support."""
    secrets_to_try = [settings.SECRET_KEY]
    if settings.SECRET_KEY_PREVIOUS:
        secrets_to_try.append(settings.SECRET_KEY_PREVIOUS)

    for secret in secrets_to_try:
        try:
            payload = jwt.decode(token, secret, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError:
            continue
    return None


def hash_token(token: str) -> str:
    """Hash a token for secure storage (e.g., refresh tokens in DB)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def is_token_expired(payload: dict) -> bool:
    """Check if a decoded token payload is expired."""
    exp = payload.get("exp")
    if not exp:
        return True
    return datetime.now(timezone.utc).timestamp() > exp
