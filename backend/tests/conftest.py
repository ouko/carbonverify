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
from sqlalchemy import JSON, String, Text

# Set test database URL BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Mock libmagic before any imports
mock_magic = MagicMock()
mock_magic.from_buffer = lambda buf, mime=False: "application/octet-stream"
sys.modules["magic"] = mock_magic

# Patch PostgreSQL-specific types for SQLite compatibility
import app.models as models_module
for attr_name in dir(models_module):
    obj = getattr(models_module, attr_name)
    if isinstance(obj, type) and hasattr(obj, '__tablename__'):
        for col in obj.__table__.columns:
            if hasattr(col.type, '__visit_name__') and col.type.__visit_name__ == 'JSONB':
                col.type = JSON()
            if hasattr(col.type, '__visit_name__') and col.type.__visit_name__ == 'ARRAY':
                col.type = JSON()
            if hasattr(col.type, '__visit_name__') and col.type.__visit_name__ == 'UUID':
                col.type = String(36)

from app.main import app
from app.database import Base, get_db
from app.auth.dependencies import get_current_user
from app.models import User, UserRoleEnum

# Register UUID adapter for sqlite3
import sqlite3
sqlite3.register_adapter(uuid.UUID, lambda u: str(u))
sqlite3.register_converter("uuid", lambda s: uuid.UUID(s.decode() if isinstance(s, bytes) else s))

# Add bind parameter processing for UUID -> String in SQLAlchemy
from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PGUUID

class StringUUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

# Re-patch UUID columns with proper bind processing
for attr_name in dir(models_module):
    obj = getattr(models_module, attr_name)
    if isinstance(obj, type) and hasattr(obj, '__tablename__'):
        for col in obj.__table__.columns:
            if isinstance(col.type, String) and col.name.endswith('_id') and col.name != 'id':
                # Foreign keys already patched to String
                pass
            elif hasattr(col.type, '__visit_name__') and col.type.__visit_name__ == 'UUID':
                # Already patched above, but let's ensure it's consistent
                pass


def _create_mock_user(role: UserRoleEnum = UserRoleEnum.admin, suffix: str = ""):
    user = User(
        id=uuid.uuid4(),
        email=f"test{suffix}@carbonverify.io",
        name="Test User",
        role=role,
        mfa_enabled=False,
        hashed_password="hashed",
    )
    return user


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
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
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(db_session):
    mock_user = _create_mock_user(UserRoleEnum.admin, suffix=str(uuid.uuid4())[:8])
    db_session.add(mock_user)
    await db_session.commit()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, mock_user

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
