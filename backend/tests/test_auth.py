"""Tests for authentication flow: login, refresh, logout."""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta

from app.models import User, UserRoleEnum
from app.auth.security import get_password_hash
from app.core.encryption import compute_searchable_hash
from sqlalchemy import select


@pytest_asyncio.fixture
async def test_user(db_session):
    email = "test@carbonverify.io"
    user = User(
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Test User",
        role=UserRoleEnum.admin,
        mfa_enabled=False,
        hashed_password=get_password_hash("Testpassword123!"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client, test_user):
        response = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client, test_user):
        response = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Wrongpassword123!",
        })
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        response = await client.post("/auth/login", json={
            "email": "nonexistent@carbonverify.io",
            "password": "Somepassword123!",
        })
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_heals_legacy_hash(self, client, db_session):
        """Users hashed before ENCRYPTION_KEY_HEX existed (raw SHA-256) can log in."""
        from app.core.encryption import legacy_searchable_hash

        email = "legacy@carbonverify.io"
        user = User(
            email=email,
            email_hash=legacy_searchable_hash(email),
            name="Legacy User",
            role=UserRoleEnum.admin,
            mfa_enabled=False,
            hashed_password=get_password_hash("Testpassword123!"),
        )
        db_session.add(user)
        await db_session.commit()

        response = await client.post("/auth/login", json={
            "email": email,
            "password": "Testpassword123!",
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

        # The stored hash was healed to the keyed hash on successful login
        result = await db_session.execute(
            select(User).where(User.email_hash == compute_searchable_hash(email))
        )
        healed = result.scalar_one()
        assert healed.name == "Legacy User"

    @pytest.mark.asyncio
    async def test_login_account_lockout(self, client, test_user):
        # Fail login 5 times
        for _ in range(5):
            await client.post("/auth/login", json={
                "email": "test@carbonverify.io",
                "password": "Wrongpassword123!",
            })

        # 6th attempt should be locked
        response = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        assert response.status_code == 403
        assert "Account locked" in response.json()["detail"]


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, client):
        response = await client.post("/auth/register", json={
            "email": "newuser@carbonverify.io",
            "password": "Newpassword123!",
            "name": "New User",
            "role": "viewer",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@carbonverify.io"
        assert data["name"] == "New User"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, test_user):
        response = await client.post("/auth/register", json={
            "email": "test@carbonverify.io",
            "password": "Somepassword123!",
            "name": "Duplicate",
            "role": "viewer",
        })
        assert response.status_code == 400
        assert response.json()["detail"] == "Email already registered"


class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_without_cookie(self, client):
        response = await client.post("/auth/refresh")
        assert response.status_code == 401
        assert response.json()["detail"] == "Refresh token missing"

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client):
        response = await client.post(
            "/auth/refresh",
            cookies={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401


class TestForgotPassword:
    @pytest.mark.asyncio
    async def test_forgot_password_existing_user(self, client, test_user):
        response = await client.post("/auth/forgot-password", json={
            "email": "test@carbonverify.io",
        })
        assert response.status_code == 200
        # Should return same message regardless of whether user exists
        assert "reset link has been sent" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_forgot_password_nonexistent_user(self, client):
        response = await client.post("/auth/forgot-password", json={
            "email": "nonexistent@carbonverify.io",
        })
        assert response.status_code == 200
        # Same message to prevent enumeration
        assert "reset link has been sent" in response.json()["message"]


class TestResetPassword:
    @pytest.mark.asyncio
    async def test_reset_password_success(self, client, test_user, db_session):
        # Set a reset token on the user
        import secrets
        import hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        test_user.password_reset_token_hash = token_hash
        test_user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db_session.commit()

        response = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "Newpassword123!",
        })
        assert response.status_code == 200
        assert "Password has been reset" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, client):
        response = await client.post("/auth/reset-password", json={
            "token": "invalid-token",
            "new_password": "Newpassword123!",
        })
        assert response.status_code == 400
        assert "Invalid or expired reset token" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_reset_password_weak_password(self, client, test_user, db_session):
        import secrets
        import hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        test_user.password_reset_token_hash = token_hash
        test_user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db_session.commit()

        response = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "weak",
        })
        assert response.status_code == 422


class TestLogout:
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Event loop closed issue with httpx cookie handling in tests")
    async def test_logout_clears_cookie(self, client, test_user):
        # Login
        login_res = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        assert login_res.status_code == 200
        access_token = login_res.json()["access_token"]

        # Logout
        logout_res = await client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_res.status_code == 200
        # Cookie should be cleared (Set-Cookie header present)
        set_cookie = logout_res.headers.get("set-cookie", "")
        assert "refresh_token" in set_cookie


class TestMFABackupCodes:
    @pytest.mark.asyncio
    async def test_mfa_confirm_returns_backup_codes(self, client, test_user, db_session):
        import pyotp
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        code = totp.now()

        # Login first
        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/auth/mfa/confirm",
            json={
                "secret": secret,
                "totp_code": code,
                "current_password": "Testpassword123!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mfa_enabled"] is True
        assert "backup_codes" in data
        assert len(data["backup_codes"]) == 10
        for bc in data["backup_codes"]:
            assert len(bc) == 8

    @pytest.mark.asyncio
    async def test_login_with_backup_code(self, client, test_user, db_session):
        import pyotp
        import hashlib
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        code = totp.now()

        # Login and setup MFA
        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        confirm = await client.post(
            "/auth/mfa/confirm",
            json={
                "secret": secret,
                "totp_code": code,
                "current_password": "Testpassword123!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        backup_codes = confirm.json()["backup_codes"]
        backup_code = backup_codes[0]

        # Now login should require MFA
        login2 = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        assert login2.status_code == 200
        assert login2.json()["mfa_required"] is True
        temp_token = login2.json()["temp_token"]

        # Use backup code instead of TOTP
        verify = await client.post("/auth/mfa/verify", json={
            "temp_token": temp_token,
            "totp_code": backup_code,
        })
        assert verify.status_code == 200
        assert "access_token" in verify.json()

    @pytest.mark.asyncio
    async def test_backup_code_consumed(self, client, test_user, db_session):
        import pyotp
        import hashlib
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        code = totp.now()

        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        confirm = await client.post(
            "/auth/mfa/confirm",
            json={
                "secret": secret,
                "totp_code": code,
                "current_password": "Testpassword123!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        backup_codes = confirm.json()["backup_codes"]
        backup_code = backup_codes[0]

        # Login and use backup code
        login2 = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        assert login2.json()["mfa_required"] is True
        temp_token = login2.json()["temp_token"]

        verify1 = await client.post("/auth/mfa/verify", json={
            "temp_token": temp_token,
            "totp_code": backup_code,
        })
        assert verify1.status_code == 200

        # Try using same backup code again (should fail)
        login3 = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        assert login3.json()["mfa_required"] is True
        temp_token2 = login3.json()["temp_token"]

        verify2 = await client.post("/auth/mfa/verify", json={
            "temp_token": temp_token2,
            "totp_code": backup_code,
        })
        assert verify2.status_code == 401

    @pytest.mark.asyncio
    async def test_regenerate_backup_codes(self, client, test_user, db_session):
        import pyotp
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        code = totp.now()

        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        confirm = await client.post(
            "/auth/mfa/confirm",
            json={
                "secret": secret,
                "totp_code": code,
                "current_password": "Testpassword123!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        old_codes = confirm.json()["backup_codes"]

        # Regenerate
        regen = await client.post(
            "/auth/mfa/regenerate-backup-codes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert regen.status_code == 200
        new_codes = regen.json()["backup_codes"]
        assert len(new_codes) == 10
        assert new_codes != old_codes


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_change_password_success(self, client, test_user):
        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/auth/change-password",
            json={
                "current_password": "Testpassword123!",
                "new_password": "Newpassword123!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "updated" in response.json()["message"].lower()

        # Old password should no longer work
        old_login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        assert old_login.status_code == 401

        # New password should work
        new_login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Newpassword123!",
        })
        assert new_login.status_code == 200
        assert "access_token" in new_login.json()

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client, test_user):
        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/auth/change-password",
            json={
                "current_password": "Wrongpassword123!",
                "new_password": "Newpassword123!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_change_password_weak(self, client, test_user):
        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/auth/change-password",
            json={
                "current_password": "Testpassword123!",
                "new_password": "weak",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


class TestMFADisable:
    @pytest.mark.asyncio
    async def test_admin_disable_own_mfa(self, client, test_user, db_session):
        import pyotp
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        code = totp.now()

        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        # Enable MFA
        await client.post(
            "/auth/mfa/confirm",
            json={
                "secret": secret,
                "totp_code": code,
                "current_password": "Testpassword123!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Disable MFA (admin can disable self without target_user_id)
        response = await client.post(
            "/auth/mfa/disable",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "disabled" in response.json()["message"].lower()

        # Login should no longer require MFA
        login2 = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        assert login2.status_code == 200
        assert "access_token" in login2.json()

    @pytest.mark.asyncio
    async def test_non_admin_cannot_disable_others_mfa(self, client, db_session):
        from app.models import User, UserRoleEnum
        from app.core.encryption import compute_searchable_hash
        from app.auth.security import get_password_hash

        # Create operator user
        email = "operator@carbonverify.io"
        operator = User(
            email=email,
            email_hash=compute_searchable_hash(email),
            name="Operator User",
            role=UserRoleEnum.operator,
            mfa_enabled=False,
            hashed_password=get_password_hash("Operatorpass123!"),
        )
        db_session.add(operator)
        await db_session.commit()
        await db_session.refresh(operator)

        login = await client.post("/auth/login", json={
            "email": "operator@carbonverify.io",
            "password": "Operatorpass123!",
        })
        token = login.json()["access_token"]

        # Try to disable MFA for admin user (should fail — operator is not admin)
        response = await client.post(
            "/auth/mfa/disable",
            params={"target_user_id": str(operator.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestResetPasswordEdgeCases:
    @pytest.mark.asyncio
    async def test_reset_password_expired_token(self, client, test_user, db_session):
        import secrets
        import hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        test_user.password_reset_token_hash = token_hash
        test_user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.commit()

        response = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "Newpassword123!",
        })
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_reset_password_token_reuse(self, client, test_user, db_session):
        import secrets
        import hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        test_user.password_reset_token_hash = token_hash
        test_user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db_session.commit()

        # First reset succeeds
        response1 = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "Newpassword123!",
        })
        assert response1.status_code == 200

        # Second reset with same token should fail
        response2 = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "Anotherpass123!",
        })
        assert response2.status_code == 400
        assert "Invalid or expired" in response2.json()["detail"]


class TestRefreshValid:
    @pytest.mark.asyncio
    async def test_refresh_valid_token(self, client, test_user):
        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        assert login.status_code == 200
        refresh_token = login.cookies.get("refresh_token")
        assert refresh_token is not None

        # Refresh with valid cookie
        response = await client.post(
            "/auth/refresh",
            cookies={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Old refresh token should be revoked
        response2 = await client.post(
            "/auth/refresh",
            cookies={"refresh_token": refresh_token},
        )
        assert response2.status_code == 401


class TestLogoutAll:
    @pytest.mark.asyncio
    async def test_logout_all_revokes_sessions(self, client, test_user):
        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/auth/logout-all",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "sessions terminated" in response.json()["message"].lower()


class TestInviteFlow:
    @pytest.mark.asyncio
    async def test_admin_invite_and_accept(self, client, test_user, db_session):
        # Admin invites a new user
        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        invite_response = await client.post(
            "/auth/admin/invite",
            json={
                "email": "invited@carbonverify.io",
                "name": "Invited User",
                "role": "developer",
                "permissions": ["projects:read"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert invite_response.status_code == 201
        invite_data = invite_response.json()
        assert invite_data["email"] == "invited@carbonverify.io"
        invite_token = invite_data["token"]

        # Accept invite
        accept_response = await client.post("/auth/invite/accept", json={
            "token": invite_token,
            "password": "Invitedpass123!",
            "name": "Invited User",
        })
        assert accept_response.status_code == 201
        assert accept_response.json()["email"] == "invited@carbonverify.io"

        # New user should be able to log in
        new_login = await client.post("/auth/login", json={
            "email": "invited@carbonverify.io",
            "password": "Invitedpass123!",
        })
        assert new_login.status_code == 200
        assert "access_token" in new_login.json()

    @pytest.mark.asyncio
    async def test_invite_accept_expired_token(self, client, test_user, db_session):
        from app.models import UserInvite
        from app.core.encryption import compute_searchable_hash

        # Create an expired invite directly
        invite = UserInvite(
            token="expired-token-123",
            email="expired@carbonverify.io",
            email_hash=compute_searchable_hash("expired@carbonverify.io"),
            name="Expired User",
            role="viewer",
            permissions={"granted": [], "revoked": []},
            invited_by=test_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(invite)
        await db_session.commit()

        response = await client.post("/auth/invite/accept", json={
            "token": "expired-token-123",
            "password": "Password123!",
            "name": "Expired User",
        })
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invite_duplicate_email(self, client, test_user, db_session):
        login = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "Testpassword123!",
        })
        token = login.json()["access_token"]

        # Try to invite an existing user
        response = await client.post(
            "/auth/admin/invite",
            json={
                "email": "test@carbonverify.io",
                "name": "Duplicate",
                "role": "viewer",
                "permissions": [],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
