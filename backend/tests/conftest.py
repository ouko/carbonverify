import asyncio
import os
import sys
import uuid
from unittest.mock import MagicMock
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import JSON, String, TypeDecorator

# Set test environment variables BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test-whatsapp-token"
os.environ["IOT_WEBHOOK_API_KEY"] = "test-iot-api-key"
os.environ["ENVIRONMENT"] = "test"
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"

# Mock libmagic before any imports
mock_magic = MagicMock()
mock_magic.from_buffer = lambda buf, mime=False: "application/octet-stream"
sys.modules["magic"] = mock_magic


class UUIDAsString(TypeDecorator):
    """Store UUIDs as strings but return them as UUID objects."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value)
        return value


# Patch PostgreSQL-specific types for SQLite compatibility
import app.models as models_module  # noqa: E402
import app.validation_engine.models as validation_models_module  # noqa: E402

for models_mod in [models_module, validation_models_module]:
    for attr_name in dir(models_mod):
        obj = getattr(models_mod, attr_name)
        if isinstance(obj, type) and hasattr(obj, '__tablename__'):
            for col in obj.__table__.columns:
                if hasattr(col.type, '__visit_name__') and col.type.__visit_name__ == 'JSONB':
                    col.type = JSON()
                if hasattr(col.type, '__visit_name__') and col.type.__visit_name__ == 'ARRAY':
                    col.type = JSON()
                if hasattr(col.type, '__visit_name__') and col.type.__visit_name__ == 'UUID':
                    col.type = UUIDAsString()

from app.main import app  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.auth.dependencies import get_current_user, get_current_user_or_api_key  # noqa: E402
from app.auth.security import create_access_token  # noqa: E402
from app.models import User, UserRoleEnum  # noqa: E402

# Register UUID adapter for sqlite3
import sqlite3  # noqa: E402
sqlite3.register_adapter(uuid.UUID, lambda u: str(u))
sqlite3.register_converter("uuid", lambda s: uuid.UUID(s.decode() if isinstance(s, bytes) else s))


from app.core.encryption import compute_searchable_hash

def _create_mock_user(role: UserRoleEnum = UserRoleEnum.admin, suffix: str = ""):
    email = f"test{suffix}@carbonverify.io"
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=compute_searchable_hash(email),
        name="Test User",
        role=role,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    return user


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    """Create a fresh in-memory engine for each test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def async_db_session(db_session):
    """Alias for db_session used by newer tests."""
    yield db_session


@pytest_asyncio.fixture
async def client(engine):
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(engine):
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        mock_user = _create_mock_user(UserRoleEnum.admin, suffix=str(uuid.uuid4())[:8])
        session.add(mock_user)
        await session.commit()

    async def override_get_db():
        async with async_session() as session:
            yield session

    async def override_get_current_user():
        async with async_session() as session:
            result = await session.execute(
                __import__("sqlalchemy").select(User).where(User.id == mock_user.id)
            )
            return result.scalar_one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_user_or_api_key] = override_get_current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, mock_user

    app.dependency_overrides.clear()


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def operator_headers(engine):
    """Return Authorization headers for a freshly-created operator user."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id = uuid.uuid4()
    async with async_session() as session:
        user = User(
            id=user_id,
            email=f"operator{user_id.hex[:8]}@carbonverify.io",
            email_hash=compute_searchable_hash(f"operator{user_id.hex[:8]}@carbonverify.io"),
            name="Test Operator",
            role=UserRoleEnum.operator,
            mfa_enabled=False,
            hashed_password="hashed",
        )
        session.add(user)
        await session.commit()
    token = create_access_token(str(user_id))
    return {"Authorization": f"Bearer {token}"}
