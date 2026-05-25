from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import get_settings

settings = get_settings()

_engine_kwargs = {
    "echo": settings.ENVIRONMENT == "development",
    "future": True,
}

# PostgreSQL-specific connection pooling
if settings.DATABASE_URL.startswith("postgresql"):
    _engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 30,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "connect_args": {"server_settings": {"jit": "off"}},
    })

engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
