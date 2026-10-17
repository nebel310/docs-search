from typing import Any, Protocol

from app.core.exceptions import DocumentNotFoundError
from app.core.logging import get_logger
from app.repositories.es.document import SearchRepository
from app.repositories.pg.document import DocumentRepository


logger = get_logger(__name__)


class DocumentCacheProtocol(Protocol):
    """Протокол кэша документа для инвалидации"""

    async def invalidate(self, doc_id: int) -> None:
        """Удаляет документ из кэша по id"""
        ...


class DocumentService:
    """Сервис управления документами"""

    def __init__(
        self,
        document_repository: DocumentRepository,
        search_repository: SearchRepository,
        cache: DocumentCacheProtocol | None = None,
    ) -> None:
        """Сохраняет репозитории и опциональный кэш"""
        self._document_repository = document_repository
        self._search_repository = search_repository
        self._cache = cache

    async def delete(self, doc_id: int) -> None:
        """Удаляет документ из PG, кэша и ES"""
        deleted = await self._document_repository.delete(doc_id)
        if not deleted:
            raise DocumentNotFoundError(f"Document {doc_id} not found")
        if self._cache is not None:
            await self._cache.invalidate(doc_id)
        try:
            await self._search_repository.delete(doc_id)
        except Exception as exc:
            logger.warning("es_delete_failed", doc_id=doc_id, error=str(exc))