from collections.abc import AsyncIterator
from typing import Annotated

from elasticsearch import AsyncElasticsearch
from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.document_cache import DocumentCache
from app.core.config import Settings, get_settings
from app.repositories.es.document import SearchRepository
from app.repositories.pg.document import DocumentRepository
from app.services.document_service import DocumentCacheProtocol, DocumentService
from app.services.search_service import SearchService


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_es_client(request: Request) -> AsyncElasticsearch:
    """Возвращает ES-клиент из состояния приложения"""
    return request.app.state.es_client


def get_redis(request: Request) -> Redis | None:
    """Возвращает Redis-клиент из состояния приложения"""
    return getattr(request.app.state, "redis", None)


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """Возвращает фабрику сессий из состояния приложения"""
    return request.app.state.session_factory


def get_cache(request: Request) -> DocumentCacheProtocol | None:
    """Возвращает кэш документов из состояния приложения"""
    return getattr(request.app.state, "cache", None)


async def get_session(
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[AsyncSession]:
    """Открывает сессию, коммитит при успехе и откатывает при ошибке"""
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


SessionDep = Annotated[AsyncSession, Depends(get_session)]
EsClientDep = Annotated[AsyncElasticsearch, Depends(get_es_client)]
RedisDep = Annotated[Redis | None, Depends(get_redis)]
CacheDep = Annotated[DocumentCacheProtocol | None, Depends(get_cache)]


def get_document_repository(session: SessionDep) -> DocumentRepository:
    """Создаёт репозиторий документов PG"""
    return DocumentRepository(session)


def get_search_repository(client: EsClientDep, settings: SettingsDep) -> SearchRepository:
    """Создаёт репозиторий поиска ES"""
    return SearchRepository(client, settings.elasticsearch_index)


DocumentRepositoryDep = Annotated[DocumentRepository, Depends(get_document_repository)]
SearchRepositoryDep = Annotated[SearchRepository, Depends(get_search_repository)]


def get_search_service(
    search_repository: SearchRepositoryDep,
    document_repository: DocumentRepositoryDep,
    settings: SettingsDep,
) -> SearchService:
    """Создаёт SearchService с зависимостями"""
    return SearchService(search_repository, document_repository, settings)


def get_document_service(
    document_repository: DocumentRepositoryDep,
    search_repository: SearchRepositoryDep,
    cache: CacheDep,
) -> DocumentService:
    """Создаёт DocumentService с зависимостями"""
    return DocumentService(document_repository, search_repository, cache)


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]