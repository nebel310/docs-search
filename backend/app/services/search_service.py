from app.core.config import Settings
from app.db.models import Document
from app.repositories.es.document import SearchRepository
from app.repositories.pg.document import DocumentRepository


class SearchService:
    """Сервис поиска документов"""

    def __init__(
        self,
        search_repository: SearchRepository,
        document_repository: DocumentRepository,
        settings: Settings,
    ) -> None:
        """Сохраняет репозитории и настройки"""
        self._search_repository = search_repository
        self._document_repository = document_repository
        self._settings = settings

    async def search(self, query: str) -> list[Document]:
        """Ищет документы по тексту и возвращает ограниченный список"""
        ids = await self._search_repository.search(query, self._settings.search_candidates)
        if not ids:
            return []
        documents = await self._document_repository.get_by_ids(ids)
        return documents[: self._settings.search_result_limit]