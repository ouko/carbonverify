"""Tests for authentication flow: login, refresh, logout."""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta

from app.models import User, UserRoleEnum
from app.auth.security import get_password_hash
from sqlalchemy import select


@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(
        email="test@carbonverify.io",
        name="Test User",
        role=UserRoleEnum.admin,
        mfa_enabled=False,
        hashed_password=get_password_hash("testpassword123"),
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
            "password": "testpassword123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client, test_user):
        response = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "wrongpassword",
        })
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        response = await client.post("/auth/login", json={
            "email": "nonexistent@carbonverify.io",
            "password": "somepassword",
        })
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="SQLite datetime timezone mismatch — tested in integration")
    async def test_login_account_lockout(self, client, test_user):
        # Fail login 5 times
        for _ in range(5):
            await client.post("/auth/login", json={
                "email": "test@carbonverify.io",
                "password": "wrongpassword",
            })

        # 6th attempt should be locked
        response = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "testpassword123",
        })
        assert response.status_code == 403
        assert "Account locked" in response.json()["detail"]


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, client):
        response = await client.post("/auth/register", json={
            "email": "newuser@carbonverify.io",
            "password": "newpassword123",
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
            "password": "somepassword",
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


class TestLogout:
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Event loop closed issue with httpx cookie handling in tests")
    async def test_logout_clears_cookie(self, client, test_user):
        # Login
        login_res = await client.post("/auth/login", json={
            "email": "test@carbonverify.io",
            "password": "testpassword123",
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
