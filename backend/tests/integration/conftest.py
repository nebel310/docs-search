import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from elasticsearch import AsyncElasticsearch
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from testcontainers.community.elasticsearch import ElasticSearchContainer
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from app.cache.redis_client import create_redis_client
from app.core.config import Settings, get_settings
from app.db.session import create_engine, create_session_factory
from app.search.client import create_es_client
from app.search.index import create_index, delete_index


BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
ALEMBIC_DIR = BACKEND_ROOT / "alembic"
TEST_INDEX = "documents_test"


@pytest.fixture(scope="session")
def pg_container() -> Iterator[PostgresContainer]:
    """Поднимает контейнер PostgreSQL на всю сессию"""
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def es_container() -> Iterator[ElasticSearchContainer]:
    """Поднимает контейнер Elasticsearch на всю сессию"""
    with ElasticSearchContainer(
        "docker.elastic.co/elasticsearch/elasticsearch:8.15.0"
    ) as container:
        yield container


@pytest.fixture(scope="session")
def redis_container() -> Iterator[RedisContainer]:
    """Поднимает контейнер Redis на всю сессию"""
    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def pg_url(pg_container: PostgresContainer) -> str:
    """Возвращает asyncpg-DSN для тестового контейнера"""
    url = pg_container.get_connection_url()
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest.fixture(scope="session")
def es_url(es_container: ElasticSearchContainer) -> str:
    """Возвращает HTTP-URL тестового Elasticsearch"""
    host = es_container.get_container_host_ip()
    port = es_container.get_exposed_port(9200)
    return f"http://{host}:{port}"


@pytest.fixture(scope="session")
def redis_url(redis_container: RedisContainer) -> str:
    """Возвращает DSN тестового Redis"""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


@pytest.fixture(scope="session", autouse=True)
def _configure_env(
    pg_url: str,
    es_url: str,
    redis_url: str,
) -> Iterator[None]:
    """Прокидывает URL тестовых контейнеров в env и сбрасывает кэш Settings"""
    keys = ("DATABASE_URL", "ELASTICSEARCH_URL", "REDIS_URL", "ELASTICSEARCH_INDEX")
    saved = {key: os.environ.get(key) for key in keys}
    os.environ["DATABASE_URL"] = pg_url
    os.environ["ELASTICSEARCH_URL"] = es_url
    os.environ["REDIS_URL"] = redis_url
    os.environ["ELASTICSEARCH_INDEX"] = TEST_INDEX
    get_settings.cache_clear()
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(_configure_env: None) -> Iterator[None]:
    """Применяет Alembic-миграции до тестов и откатывает после"""
    config = AlembicConfig(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")


@pytest.fixture(scope="session")
async def pg_engine(pg_url: str) -> AsyncIterator[AsyncEngine]:
    """Создаёт и закрывает async-движок с продакшеновой конфигурацией пула"""
    settings = Settings(_env_file=None, database_url=pg_url)
    engine = create_engine(settings)
    yield engine
    await engine.dispose()


@pytest.fixture
async def pg_session_factory(
    pg_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker]:
    """Отдаёт продакшеновую фабрику сессий и чистит таблицу после теста"""
    factory = create_session_factory(pg_engine)
    yield factory
    async with factory() as session:
        await session.execute(text("TRUNCATE documents RESTART IDENTITY CASCADE"))
        await session.commit()


@pytest.fixture
async def es_client(es_url: str) -> AsyncIterator[AsyncElasticsearch]:
    """Отдаёт продакшеновый ES-клиент и пересоздаёт тестовый индекс"""
    settings = Settings(
        _env_file=None,
        elasticsearch_url=es_url,
        elasticsearch_index=TEST_INDEX,
    )
    client = create_es_client(settings)
    await delete_index(client, TEST_INDEX)
    await create_index(client, TEST_INDEX)
    yield client
    await delete_index(client, TEST_INDEX)
    await client.close()


@pytest.fixture
async def redis_client(redis_url: str) -> AsyncIterator[Redis]:
    """Отдаёт продакшеновый Redis-клиент и чистит базу после теста"""
    settings = Settings(_env_file=None, redis_url=redis_url)
    client = create_redis_client(settings)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()