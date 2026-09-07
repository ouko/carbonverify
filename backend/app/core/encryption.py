"""Field-level encryption for PII using Fernet (symmetric AES-128-CBC + HMAC)."""

import base64
import hashlib
import hmac
from typing import Optional
from cryptography.fernet import Fernet
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EncryptionConfigurationError(Exception):
    """Raised when encryption is required but not properly configured."""

    pass


def _encryption_required() -> bool:
    """Encryption is mandatory in production and staging; lenient in dev/test."""
    return settings.ENVIRONMENT in ("production", "staging")


def compute_searchable_hash(value: str, key_hex: Optional[str] = None) -> str:
    """Create a deterministic HMAC-SHA256 hash for searchable encrypted fields.

    This allows exact-match lookups on encrypted columns without exposing
    the plaintext. Uses the same key as field encryption for simplicity.
    """
    raw_key = key_hex or settings.ENCRYPTION_KEY_HEX
    if not raw_key:
        if _encryption_required():
            raise EncryptionConfigurationError(
                "ENCRYPTION_KEY_HEX is required in production/staging to compute keyed searchable hashes"
            )
        # Fallback only in dev/test: return raw SHA-256 (deterministic but not keyed)
        return legacy_searchable_hash(value)
    key_bytes = bytes.fromhex(raw_key)
    return hmac.new(key_bytes, value.lower().encode("utf-8"), hashlib.sha256).hexdigest()


def legacy_searchable_hash(value: str) -> str:
    """Raw SHA-256 of the lowercased value, as stored by pre-key deployments.

    Rows written before ENCRYPTION_KEY_HEX was configured carry this hash in
    their *_hash columns; lookups must match it (and can heal it to the keyed
    hash) or those rows become unreachable once a key is configured.
    """
    return hashlib.sha256(value.lower().encode("utf-8")).hexdigest()


class FieldEncryption:
    """Encrypt/decrypt sensitive fields at the application layer.

    Uses Fernet which provides:
    - AES-128 in CBC mode for confidentiality
    - HMAC-SHA256 for authenticity
    - PBKDF2 key derivation
    """

    def __init__(self, key_hex: Optional[str] = None):
        raw_key = key_hex or settings.ENCRYPTION_KEY_HEX
        if not raw_key:
            if _encryption_required():
                raise EncryptionConfigurationError(
                    "ENCRYPTION_KEY_HEX is required in production/staging for PII field encryption"
                )
            logger.warning("field_encryption_no_key")
            self._fernet = None
            return

        # Fernet requires a 32-byte base64-encoded key
        try:
            key_bytes = bytes.fromhex(raw_key)
            if len(key_bytes) != 32:
                raise ValueError(f"Encryption key must be 32 bytes (64 hex chars), got {len(key_bytes)}")
            self._fernet = Fernet(base64.urlsafe_b64encode(key_bytes))
        except Exception as exc:
            logger.error("field_encryption_init_failed", error=str(exc))
            if _encryption_required():
                raise EncryptionConfigurationError(f"Invalid ENCRYPTION_KEY_HEX: {exc}") from exc
            self._fernet = None

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """Encrypt a string value. Returns None if encryption is disabled."""
        if plaintext is None:
            return None
        if not self.enabled:
            return plaintext
        try:
            token = self._fernet.encrypt(plaintext.encode("utf-8"))
            return token.decode("utf-8")
        except Exception as exc:
            logger.error("field_encryption_encrypt_failed", error=str(exc))
            raise

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        """Decrypt an encrypted string value."""
        if ciphertext is None:
            return None
        if not self.enabled:
            return ciphertext
        try:
            plaintext = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return plaintext.decode("utf-8")
        except Exception as exc:
            logger.error("field_encryption_decrypt_failed", error=str(exc))
            raise

    def decrypt_fallback(self, ciphertext: Optional[str]) -> Optional[str]:
        """Decrypt a value, falling back to the raw value on failure.

        For legacy rows written before field encryption was enabled (plaintext
        at rest) or rows written under a rotated key: strict decryption would
        raise and break the whole read, so column types use this instead and
        log loudly. Callers that must fail closed should use decrypt().
        """
        if ciphertext is None:
            return None
        if not self.enabled:
            return ciphertext
        try:
            plaintext = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return plaintext.decode("utf-8")
        except Exception as exc:
            logger.warning(
                "field_encryption_decrypt_fallback",
                error=str(exc),
                hint="value is not decryptable with the configured key; returning raw value",
            )
            return ciphertext


# Global instance
_field_encryption: Optional[FieldEncryption] = None


def get_field_encryption() -> FieldEncryption:
    global _field_encryption
    if _field_encryption is None:
        _field_encryption = FieldEncryption()
    return _field_encryption
