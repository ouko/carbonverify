"""
Multi-Factor Authentication (TOTP) for CarbonVerify.

Supports Google Authenticator / Authy compatible TOTP codes.
MFA is required for admin and operator roles by default.
"""

import pyotp
import qrcode
import io
import base64
from typing import Optional

from app.config import get_settings

settings = get_settings()


def generate_mfa_secret() -> str:
    """Generate a new TOTP secret."""
    return pyotp.random_base32()


def get_totp(secret: str) -> pyotp.TOTP:
    """Get a TOTP verifier for a secret."""
    return pyotp.TOTP(secret, issuer=settings.MFA_ISSUER_NAME)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against a secret."""
    if not secret or not code:
        return False
    totp = get_totp(secret)
    return totp.verify(code, valid_window=1)


def generate_qr_code_uri(secret: str, email: str) -> str:
    """Generate a QR code provisioning URI for authenticator apps."""
    totp = get_totp(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.MFA_ISSUER_NAME)


def generate_qr_code_png(secret: str, email: str) -> str:
    """
    Generate a base64-encoded PNG QR code.

    Returns a data URI that can be embedded directly in an <img> tag.
    """
    uri = generate_qr_code_uri(secret, email)
    qr = qrcode.make(uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def is_mfa_required(role: str) -> bool:
    """Check if MFA is required for a given role."""
    required_roles = [r.strip().lower() for r in settings.MFA_REQUIRED_ROLES.split(",")]
    return role.lower() in required_roles
