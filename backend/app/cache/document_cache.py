from redis.asyncio import Redis

from app.schemas.document import DocumentOut


CACHE_KEY_PREFIX = "doc"


class DocumentCache:
    """Кэш документов в Redis"""

    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        """Сохраняет клиент и TTL"""
        self._client = client
        self._ttl = ttl_seconds

    def _key(self, doc_id: int) -> str:
        """Формирует ключ кэша для документа"""
        return f"{CACHE_KEY_PREFIX}:{doc_id}"

    async def get(self, doc_id: int) -> DocumentOut | None:
        """Возвращает документ из кэша или None"""
        raw = await self._client.get(self._key(doc_id))
        if raw is None:
            return None
        return DocumentOut.model_validate_json(raw)

    async def set(self, doc_id: int, document: DocumentOut) -> None:
        """Кладёт документ в кэш с TTL"""
        await self._client.set(self._key(doc_id), document.model_dump_json(), ex=self._ttl)

    async def invalidate(self, doc_id: int) -> None:
        """Удаляет документ из кэша"""
        await self._client.delete(self._key(doc_id))