from typing import Any

from elasticsearch import AsyncElasticsearch

from app.search.index import (
    bulk_index_documents,
    delete_document,
    index_document,
    search_documents,
)


class SearchRepository:
    """Репозиторий поискового индекса в Elasticsearch"""

    def __init__(self, client: AsyncElasticsearch, index: str) -> None:
        """Сохраняет клиент и имя индекса"""
        self._client = client
        self._index = index

    async def search(self, query: str, size: int) -> list[int]:
        """Ищет id документов по текстовому запросу"""
        return await search_documents(self._client, self._index, query, size)

    async def index(self, doc_id: int, text: str) -> None:
        """Индексирует один документ"""
        await index_document(self._client, self._index, doc_id, text)

    async def bulk_index(self, documents: list[dict[str, Any]]) -> int:
        """Индексирует пачку документов и возвращает их количество"""
        return await bulk_index_documents(self._client, self._index, documents)

    async def delete(self, doc_id: int) -> None:
        """Удаляет документ из индекса"""
        await delete_document(self._client, self._index, doc_id)