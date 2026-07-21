from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _async_database_url() -> str:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    if settings.database_url.startswith("postgresql+asyncpg://"):
        return settings.database_url
    if settings.database_url.startswith("postgresql://"):
        return settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if settings.database_url.startswith("postgres://"):
        return settings.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    raise RuntimeError("DATABASE_URL must use PostgreSQL")


def get_engine() -> AsyncEngine | None:
    global _engine
    if _engine is None and settings.database_url:
        _engine = create_async_engine(
            _async_database_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            connect_args={"server_settings": {"application_name": "evoting-api"}},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        if engine is None:
            raise RuntimeError("DATABASE_URL is not configured")
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    if _engine is not None:
        await _engine.dispose()
