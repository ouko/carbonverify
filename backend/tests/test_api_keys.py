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


class TestApiKeyScopeValidation:
    @pytest.mark.asyncio
    async def test_creator_cannot_grant_scopes_they_dont_have(self, client, db_session):
        from app.models import User, UserRoleEnum
        from app.core.encryption import compute_searchable_hash
        from app.auth.security import get_password_hash

        # Create operator user (operators don't have system:configure by default)
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

        response = await client.post(
            "/api-keys/",
            json={"name": "Overreach Key", "scopes": ["system:configure"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_expired_api_key_rejected(self, client, admin_user, db_session):
        import hashlib
        import secrets
        from datetime import datetime, timezone, timedelta
        from app.models import ApiKey

        login = await client.post("/auth/login", json={
            "email": "admin@carbonverify.io",
            "password": "Adminpassword123!",
        })
        token = login.json()["access_token"]

        # Create key with 1 day expiry
        create = await client.post(
            "/api-keys/",
            json={"name": "Short Key", "scopes": ["projects:read"], "expires_in_days": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create.status_code == 201
        raw_key = create.json()["key"]

        # Set expiry to past directly in DB
        result = await db_session.execute(select(ApiKey).where(ApiKey.name == "Short Key"))
        key_record = result.scalar_one()
        key_record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await db_session.commit()

        # Try to use expired key
        response = await client.get(
            "/projects/",
            headers={"Authorization": f"ApiKey {raw_key}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_list_pagination(self, client, admin_user, db_session):
        import hashlib
        import secrets
        from app.models import ApiKey

        # Create multiple keys directly in DB for speed
        for i in range(5):
            raw = f"cv_{secrets.token_urlsafe(32)}"
            k = ApiKey(
                name=f"Key {i}",
                key_prefix=raw[:8],
                key_hash=hashlib.sha256(raw.encode()).hexdigest(),
                scopes=["projects:read"],
                created_by=admin_user.id,
            )
            db_session.add(k)
        await db_session.commit()

        login = await client.post("/auth/login", json={
            "email": "admin@carbonverify.io",
            "password": "Adminpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.get(
            "/api-keys/?skip=0&limit=2",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        response2 = await client.get(
            "/api-keys/?skip=2&limit=2",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2) == 2

    @pytest.mark.asyncio
    async def test_api_key_empty_scopes(self, client, admin_user):
        login = await client.post("/auth/login", json={
            "email": "admin@carbonverify.io",
            "password": "Adminpassword123!",
        })
        token = login.json()["access_token"]

        response = await client.post(
            "/api-keys/",
            json={"name": "No Scope Key", "scopes": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scopes"] == []
        assert data["key"].startswith("cv_")
