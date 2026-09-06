"""Tests for field-level encryption and the legacy-row decrypt fallback."""

import pytest

from app.core.encryption import get_field_encryption


def test_encryption_enabled_in_tests():
    assert get_field_encryption().enabled, (
        "ENCRYPTION_KEY_HEX must be configured for these tests (backend/.env)"
    )


def test_encrypt_decrypt_roundtrip():
    enc = get_field_encryption()
    token = enc.encrypt("owner@example.com")
    assert token != "owner@example.com"
    assert token.startswith("gAAAA")  # Fernet token
    assert enc.decrypt(token) == "owner@example.com"
    assert enc.decrypt_fallback(token) == "owner@example.com"


def test_decrypt_raises_on_undecryptable_value():
    enc = get_field_encryption()
    with pytest.raises(Exception):
        enc.decrypt("not-a-fernet-token")


def test_decrypt_fallback_returns_raw_on_undecryptable_value():
    """Legacy plaintext rows (pre-encryption) must read back as-is, not raise."""
    enc = get_field_encryption()
    assert enc.decrypt_fallback("legacy-plaintext@example.com") == "legacy-plaintext@example.com"
    assert enc.decrypt_fallback(None) is None
