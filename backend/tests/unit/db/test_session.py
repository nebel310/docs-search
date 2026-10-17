from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.session import MAX_OVERFLOW, POOL_SIZE, create_engine, create_session_factory


def test_create_engine_returns_async_engine() -> None:
    """Проверяет что create_engine возвращает AsyncEngine"""
    engine = create_engine(Settings(_env_file=None))
    assert isinstance(engine, AsyncEngine)


def test_create_engine_pool_size() -> None:
    """Проверяет размер пула соединений"""
    engine = create_engine(Settings(_env_file=None))
    assert engine.pool.size() == POOL_SIZE


def test_create_engine_max_overflow() -> None:
    """Проверяет значение max_overflow у пула"""
    engine = create_engine(Settings(_env_file=None))
    assert engine.pool._max_overflow == MAX_OVERFLOW


def test_create_engine_pre_ping_enabled() -> None:
    """Проверяет что pool_pre_ping включён"""
    engine = create_engine(Settings(_env_file=None))
    assert engine.pool._pre_ping is True


def test_create_engine_disables_statement_cache() -> None:
    """Проверяет что statement_cache_size=0 для PgBouncer"""
    engine = create_engine(Settings(_env_file=None))
    assert engine.sync_engine.dialect.statement_cache_size == 0


def test_create_session_factory_returns_maker() -> None:
    """Проверяет что create_session_factory возвращает async_sessionmaker"""
    engine = create_engine(Settings(_env_file=None))
    factory = create_session_factory(engine)
    assert isinstance(factory, async_sessionmaker)


def test_session_factory_expire_on_commit_false() -> None:
    """Проверяет что expire_on_commit установлен в False"""
    engine = create_engine(Settings(_env_file=None))
    factory = create_session_factory(engine)
    assert factory.kw.get("expire_on_commit") is False


async def test_factory_creates_async_session_with_settings() -> None:
    """Проверяет что фабрика создаёт AsyncSession с нужными настройками"""
    engine = create_engine(Settings(_env_file=None))
    factory = create_session_factory(engine)
    async with factory() as session:
        assert isinstance(session, AsyncSession)
        assert session.sync_session.expire_on_commit is False
    await engine.dispose()