from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings


POOL_SIZE = 5
MAX_OVERFLOW = 20


def create_engine(settings: Settings) -> AsyncEngine:
    """Создаёт асинхронный движок SQLAlchemy с пулом соединений"""
    return create_async_engine(
        settings.database_url,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создаёт фабрику асинхронных сессий"""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)