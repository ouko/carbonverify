"""Tests for API key authentication and management."""

import pytest
import pytest_asyncio

from app.models import User, UserRoleEnum, ApiKey
from app.auth.security import get_password_hash
from app.core.encryption import compute_searchable_hash
from sqlalchemy import select


@pytest_asyncio.fixture
async def admin_user(db_session):
    email = "admin@carbonverify.io"
    user = User(
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Admin User",
        role=UserRoleEnum.admin,
        mfa_enabled=False,
        hashed_password=get_password_hash("Adminpassword123!"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def api_key(db_session, admin_user):
    import hashlib
    import secrets
    raw_key = f"cv_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key = ApiKey(
        name="Test Key",
        key_prefix=raw_key[:8],
        key_hash=key_hash,
        scopes=["projects:read", "data_sources:read"],
        created_by=admin_user.id,
    )
    db_session.add(key)
    await db_session.commit()
    await db_session.refresh(key)
    return raw_key, key


class TestApiKeyAuth:
    @pytest.mark.asyncio
    async def test_api_key_access_success(self, client, api_key):
        raw_key, key = api_key
        response = await client.get(
            "/projects/",
            headers={"Authorization": f"ApiKey {raw_key}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_api_key_access_denied_scope(self, client, api_key):
        raw_key, key = api_key
        # API key has projects:read but not system:configure
        response = await client.post(
            "/api-keys/",
            json={"name": "Test Key", "scopes": ["projects:read"]},
            headers={"Authorization": f"ApiKey {raw_key}"},
        )
        assert response.status_code == 403
        assert "scope denied" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_api_key_invalid_format(self, client):
        response = await client.get(
            "/projects/",
            headers={"Authorization": "ApiKey invalid"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_invalid_key(self, client):
        response = await client.get(
            "/projects/",
            headers={"Authorization": "ApiKey cv_invalidtoken12345"},
        )
        assert response.status_code == 401


class TestApiKeyManagement:
    @pytest.mark.asyncio
    async def test_create_api_key(self, client, admin_user):
        login = await client.post("/auth/login", json={
            "email": "admin@carbonverify.io",
            "password": "Adminpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/api-keys/",
            json={"name": "Integration Key", "scopes": ["projects:read"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Integration Key"
        assert data["key"].startswith("cv_")
        assert data["key_prefix"] == data["key"][:8]

    @pytest.mark.asyncio
    async def test_create_api_key_scope_validation(self, client, admin_user):
        login = await client.post("/auth/login", json={
            "email": "admin@carbonverify.io",
            "password": "Adminpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/api-keys/",
            json={"name": "Bad Key", "scopes": ["invalid:scope"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert "Invalid scopes" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_api_keys(self, client, admin_user, api_key):
        login = await client.post("/auth/login", json={
            "email": "admin@carbonverify.io",
            "password": "Adminpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.get(
            "/api-keys/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        # Full key should never be returned
        assert "key" not in data[0]
        assert data[0]["key_prefix"] is not None

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, client, admin_user, api_key):
        raw_key, key = api_key
        login = await client.post("/auth/login", json={
            "email": "admin@carbonverify.io",
            "password": "Adminpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.delete(
            f"/api-keys/{key.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        # Key should no longer work
        response = await client.get(
            "/projects/",
            headers={"Authorization": f"ApiKey {raw_key}"},
        )
        assert response.status_code == 401
