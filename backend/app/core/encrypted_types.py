"""SQLAlchemy encrypted column types for PII."""

from typing import Optional
from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import VARCHAR

from app.core.encryption import get_field_encryption


class EncryptedString(TypeDecorator):
    """Transparently encrypts/decrypts string values at the application layer.

    Stores as VARCHAR in the database. Falls back to plaintext if encryption
    key is not configured (for development environments).
    """

    impl = VARCHAR
    cache_ok = True

    def __init__(self, length: int = 500, **kwargs):
        super().__init__(length=length, **kwargs)
        self._enc = get_field_encryption()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        encrypted = self._enc.encrypt(value)
        return encrypted

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self._enc.decrypt_fallback(value)
