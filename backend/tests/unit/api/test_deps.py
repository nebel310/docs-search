from unittest.mock import AsyncMock, MagicMock

import pytest
from elasticsearch import AsyncElasticsearch
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import (
    get_cache,
    get_document_repository,
    get_document_service,
    get_es_client,
    get_redis,
    get_search_repository,
    get_search_service,
    get_session,
    get_session_factory,
)
from app.core.config import Settings
from app.repositories.es.document import SearchRepository
from app.repositories.pg.document import DocumentRepository
from app.services.document_service import DocumentService
from app.services.search_service import SearchService


def test_get_es_client_returns_from_state() -> None:
    """Проверяет что ES-клиент берётся из app.state"""
    request = MagicMock()
    request.app.state.es_client = MagicMock(spec=AsyncElasticsearch)
    assert get_es_client(request) is request.app.state.es_client


def test_get_redis_returns_none_when_missing() -> None:
    """Проверяет что при отсутствии Redis возвращается None"""
    request = MagicMock()
    request.app.state = MagicMock(spec=[])
    assert get_redis(request) is None


def test_get_redis_returns_from_state() -> None:
    """Проверяет что Redis берётся из app.state"""
    request = MagicMock()
    request.app.state.redis = MagicMock()
    assert get_redis(request) is request.app.state.redis


def test_get_session_factory_returns_from_state() -> None:
    """Проверяет что фабрика сессий берётся из app.state"""
    request = MagicMock()
    request.app.state.session_factory = MagicMock(spec=async_sessionmaker)
    assert get_session_factory(request) is request.app.state.session_factory


def test_get_cache_returns_none_when_missing() -> None:
    """Проверяет что при отсутствии кэша возвращается None"""
    request = MagicMock()
    request.app.state = MagicMock(spec=[])
    assert get_cache(request) is None


def test_get_cache_returns_from_state() -> None:
    """Проверяет что кэш берётся из app.state"""
    request = MagicMock()
    request.app.state.cache = MagicMock()
    assert get_cache(request) is request.app.state.cache


def _session_with_context() -> tuple[MagicMock, MagicMock]:
    """Создаёт мок сессии и контекстного менеджера фабрики"""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(spec=async_sessionmaker)
    factory.return_value = cm
    return session, factory


async def test_get_session_commits_on_success() -> None:
    """Проверяет что get_session коммитит при успехе"""
    session, factory = _session_with_context()
    async for yielded in get_session(factory):
        assert yielded is session
    factory.return_value.__aexit__.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


async def test_get_session_rollbacks_on_exception() -> None:
    """Проверяет что get_session откатывает при ошибке"""
    session, factory = _session_with_context()
    gen = get_session(factory)
    await anext(gen)
    with pytest.raises(RuntimeError):
        await gen.athrow(RuntimeError("boom"))
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_get_document_repository_returns_repository() -> None:
    """Проверяет создание DocumentRepository"""
    session = MagicMock(spec=AsyncSession)
    repository = get_document_repository(session)
    assert isinstance(repository, DocumentRepository)


def test_get_search_repository_passes_index() -> None:
    """Проверяет что в SearchRepository передаётся индекс"""
    client = MagicMock(spec=AsyncElasticsearch)
    settings = Settings(_env_file=None, elasticsearch_index="docs")
    repository = get_search_repository(client, settings)
    assert isinstance(repository, SearchRepository)
    assert repository._index == "docs"


def test_get_search_service_returns_service() -> None:
    """Проверяет создание SearchService"""
    search_repository = MagicMock(spec=SearchRepository)
    document_repository = MagicMock(spec=DocumentRepository)
    settings = Settings(_env_file=None)
    service = get_search_service(search_repository, document_repository, settings)
    assert isinstance(service, SearchService)


def test_get_document_service_without_cache() -> None:
    """Проверяет создание DocumentService без кэша"""
    document_repository = MagicMock(spec=DocumentRepository)
    search_repository = MagicMock(spec=SearchRepository)
    service = get_document_service(document_repository, search_repository, None)
    assert isinstance(service, DocumentService)
    assert service._cache is None


def test_get_document_service_with_cache() -> None:
    """Проверяет создание DocumentService с кэшем"""
    document_repository = MagicMock(spec=DocumentRepository)
    search_repository = MagicMock(spec=SearchRepository)
    cache = MagicMock()
    service = get_document_service(document_repository, search_repository, cache)
    assert isinstance(service, DocumentService)
    assert service._cache is cache