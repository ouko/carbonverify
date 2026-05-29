import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User, UserRoleEnum
from app.core.encryption import compute_searchable_hash


def _create_user(role=UserRoleEnum.admin, suffix=""):
    email = f"admin{suffix}@test.io"
    return User(
        id=__import__("uuid").uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Admin User",
        role=role,
        mfa_enabled=False,
        hashed_password="hashed",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_admin_stats(engine, authenticated_client):
    ac, mock_user = authenticated_client
    res = await ac.get("/admin/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_users" in data
    assert "active_users" in data
    assert "users_by_role" in data


@pytest.mark.asyncio
async def test_admin_permissions(engine, authenticated_client):
    ac, mock_user = authenticated_client
    res = await ac.get("/admin/permissions")
    assert res.status_code == 200
    data = res.json()
    assert "permissions" in data
    assert isinstance(data["permissions"], list)
    assert len(data["permissions"]) > 0


@pytest.mark.asyncio
async def test_list_users(engine, authenticated_client):
    ac, mock_user = authenticated_client
    res = await ac.get("/users/")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(u["id"] == str(mock_user.id) for u in data)


@pytest.mark.asyncio
async def test_get_user_detail(engine, authenticated_client):
    ac, mock_user = authenticated_client
    res = await ac.get(f"/users/{mock_user.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(mock_user.id)
    assert data["email"] == mock_user.email
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_update_user(engine, authenticated_client):
    ac, mock_user = authenticated_client
    res = await ac.patch(f"/users/{mock_user.id}", json={"name": "Updated Name"})
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_deactivate_and_reactivate_user(engine, authenticated_client):
    ac, mock_user = authenticated_client

    # Create another user to deactivate
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        other = _create_user(role=UserRoleEnum.viewer, suffix="deac")
        session.add(other)
        await session.commit()
        other_id = str(other.id)

    res = await ac.delete(f"/users/{other_id}")
    assert res.status_code == 204

    res = await ac.get(f"/users/{other_id}")
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    res = await ac.post(f"/users/{other_id}/reactivate")
    assert res.status_code == 200
    assert res.json()["is_active"] is True


@pytest.mark.asyncio
async def test_invite_flow(engine, authenticated_client):
    ac, mock_user = authenticated_client

    # Admin creates invite
    res = await ac.post("/auth/admin/invite", json={
        "email": "invited@test.io",
        "name": "Invited User",
        "role": "developer",
    })
    assert res.status_code == 201
    data = res.json()
    assert "token" in data
    token = data["token"]

    # Accept invite
    res = await ac.post("/auth/invite/accept", json={
        "token": token,
        "password": "SecurePass123!",
    })
    assert res.status_code == 201
    user_data = res.json()
    assert user_data["email"] == "invited@test.io"
    assert user_data["role"] == "developer"
    assert user_data["is_active"] is True

    # Duplicate accept should fail
    res = await ac.post("/auth/invite/accept", json={
        "token": token,
        "password": "SecurePass123!",
    })
    assert res.status_code == 400
