"""Async SQLAlchemy engine + session factory with read replica support."""

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool, StaticPool

from app.config import get_settings

Base = declarative_base()

settings = get_settings()

_engine_kwargs = {
    "echo": settings.ENVIRONMENT == "development",
    "future": True,
}

# Primary (write) engine
if settings.DATABASE_URL.startswith("postgresql"):
    _engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 30,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "connect_args": {
            "server_settings": {"jit": "off", "statement_timeout": "30000"},
        },
    })
    engine: AsyncEngine = create_async_engine(
        settings.DATABASE_URL,
        **_engine_kwargs,
    )
else:
    # SQLite (tests only)
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={"check_same_thread": False},
    )

# Optional read replica engine
_read_replica_engine: Optional[AsyncEngine] = None


def get_read_replica_engine() -> Optional[AsyncEngine]:
    """Get or create the read replica engine. Returns None if no replica configured."""
    global _read_replica_engine
    if _read_replica_engine is not None:
        return _read_replica_engine

    replica_url = getattr(settings, "DATABASE_READ_REPLICA_URL", "")
    if not replica_url:
        return None

    _read_replica_engine = create_async_engine(
        replica_url,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {"jit": "off"},
            "options": "-c statement_timeout=30000",
        },
    )
    return _read_replica_engine


# Session makers
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

ReadReplicaSessionLocal: Optional[async_sessionmaker] = None


def get_read_replica_session_maker() -> Optional[async_sessionmaker]:
    """Get session maker for read replica, or None if not configured."""
    global ReadReplicaSessionLocal
    if ReadReplicaSessionLocal is not None:
        return ReadReplicaSessionLocal

    replica_engine = get_read_replica_engine()
    if replica_engine is None:
        return None

    ReadReplicaSessionLocal = async_sessionmaker(
        replica_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return ReadReplicaSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for write-primary DB sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for read-only DB sessions (uses replica if available)."""
    replica_maker = get_read_replica_session_maker()
    if replica_maker is not None:
        async with replica_maker() as session:
            try:
                yield session
            finally:
                await session.close()
    else:
        # Fallback to primary
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()


# Backwards compatibility
get_session = get_db
