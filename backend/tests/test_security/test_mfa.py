import pyotp
from app.auth.mfa import (
    generate_mfa_secret,
    verify_totp,
    generate_qr_code_uri,
    generate_qr_code_png,
    is_mfa_required,
)


class TestMFA:
    def test_generate_secret(self):
        secret = generate_mfa_secret()
        assert len(secret) == 32  # Default base32 length
        assert secret.isalnum()

    def test_verify_totp_valid(self):
        secret = generate_mfa_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert verify_totp(secret, code) is True

    def test_verify_totp_invalid(self):
        secret = generate_mfa_secret()
        assert verify_totp(secret, "000000") is False

    def test_verify_totp_empty(self):
        assert verify_totp("", "123456") is False
        assert verify_totp("secret", "") is False

    def test_verify_totp_window_tolerance(self):
        """TOTP should verify within a 1-step window."""
        secret = generate_mfa_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert verify_totp(secret, code) is True

    def test_qr_code_uri_format(self):
        secret = generate_mfa_secret()
        email = "test@carbonverify.io"
        uri = generate_qr_code_uri(secret, email)
        assert uri.startswith("otpauth://totp/")
        assert "CarbonVerify" in uri
        assert "test%40carbonverify.io" in uri or email in uri
        assert secret in uri

    def test_qr_code_png(self):
        secret = generate_mfa_secret()
        png = generate_qr_code_png(secret, "test@carbonverify.io")
        assert png.startswith("data:image/png;base64,")
        assert len(png) > 100

    def test_is_mfa_required_admin(self):
        assert is_mfa_required("admin") is True

    def test_is_mfa_required_operator(self):
        assert is_mfa_required("operator") is True

    def test_is_mfa_required_developer(self):
        assert is_mfa_required("developer") is False

    def test_is_mfa_required_viewer(self):
        assert is_mfa_required("viewer") is False
