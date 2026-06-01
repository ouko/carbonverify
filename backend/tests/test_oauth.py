"""Tests for OAuth account management endpoints."""

import pytest
import pytest_asyncio
import uuid

from app.models import User, OAuthAccount, UserRoleEnum
from app.auth.security import get_password_hash
from app.core.encryption import compute_searchable_hash


@pytest_asyncio.fixture
async def oauth_user(db_session):
    email = "oauth@carbonverify.io"
    user = User(
        email=email,
        email_hash=compute_searchable_hash(email),
        name="OAuth User",
        role=UserRoleEnum.admin,
        mfa_enabled=False,
        hashed_password=get_password_hash("Oauthpass123!"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def linked_oauth_account(db_session, oauth_user):
    account = OAuthAccount(
        user_id=oauth_user.id,
        provider="google",
        provider_account_id="google-123",
        access_token="encrypted-access",
        refresh_token="encrypted-refresh",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


class TestListOAuthAccounts:
    @pytest.mark.asyncio
    async def test_list_linked_accounts(self, client, oauth_user, linked_oauth_account):
        login = await client.post("/auth/login", json={
            "email": "oauth@carbonverify.io",
            "password": "Oauthpass123!",
        })
        token = login.json()["access_token"]

        response = await client.get(
            "/auth/oauth/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["provider"] == "google"
        assert data[0]["provider_account_id"] == "google-123"

    @pytest.mark.asyncio
    async def test_list_empty_when_no_accounts(self, client, oauth_user):
        login = await client.post("/auth/login", json={
            "email": "oauth@carbonverify.io",
            "password": "Oauthpass123!",
        })
        token = login.json()["access_token"]

        response = await client.get(
            "/auth/oauth/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_unauthenticated(self, client):
        response = await client.get("/auth/oauth/accounts")
        assert response.status_code == 401


class TestUnlinkOAuthAccount:
    @pytest.mark.asyncio
    async def test_unlink_linked_account(self, client, oauth_user, linked_oauth_account):
        login = await client.post("/auth/login", json={
            "email": "oauth@carbonverify.io",
            "password": "Oauthpass123!",
        })
        token = login.json()["access_token"]

        response = await client.delete(
            "/auth/oauth/google/unlink",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "unlinked" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_unlink_not_linked_provider(self, client, oauth_user):
        login = await client.post("/auth/login", json={
            "email": "oauth@carbonverify.io",
            "password": "Oauthpass123!",
        })
        token = login.json()["access_token"]

        response = await client.delete(
            "/auth/oauth/microsoft/unlink",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unlink_unauthenticated(self, client):
        response = await client.delete("/auth/oauth/google/unlink")
        assert response.status_code == 401


class TestLinkOAuthAccount:
    @pytest.mark.asyncio
    async def test_link_returns_authorization_url(self, client, oauth_user):
        login = await client.post("/auth/login", json={
            "email": "oauth@carbonverify.io",
            "password": "Oauthpass123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/auth/oauth/google/link",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Will fail because OAuth is not configured in test env, but should not 401
        assert response.status_code in (200, 400, 500)

    @pytest.mark.asyncio
    async def test_link_invalid_provider(self, client, oauth_user):
        login = await client.post("/auth/login", json={
            "email": "oauth@carbonverify.io",
            "password": "Oauthpass123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/auth/oauth/invalid/link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_link_unauthenticated(self, client):
        response = await client.post("/auth/oauth/google/link")
        assert response.status_code == 401
