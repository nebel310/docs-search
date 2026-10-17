from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.cache.document_cache import CACHE_KEY_PREFIX, DocumentCache
from app.schemas.document import DocumentOut


def _doc(doc_id: int = 1) -> DocumentOut:
    """Создаёт тестовую схему документа"""
    return DocumentOut(
        id=doc_id,
        rubrics=["a"],
        text="hello",
        created_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _cache(ttl: int = 300) -> tuple[DocumentCache, MagicMock]:
    """Создаёт кэш и мок Redis-клиента"""
    client = MagicMock()
    client.get = AsyncMock()
    client.set = AsyncMock()
    client.delete = AsyncMock()
    return DocumentCache(client, ttl), client


def test_key_format() -> None:
    """Проверяет формат ключа кэша"""
    cache, _ = _cache()
    assert cache._key(42) == f"{CACHE_KEY_PREFIX}:42"


async def test_get_miss_returns_none() -> None:
    """Проверяет промах кэша"""
    cache, client = _cache()
    client.get.return_value = None
    assert await cache.get(1) is None
    client.get.assert_awaited_once_with("doc:1")


async def test_get_hit_returns_document() -> None:
    """Проверяет попадание в кэш"""
    cache, client = _cache()
    document = _doc(1)
    client.get.return_value = document.model_dump_json()
    assert await cache.get(1) == document


async def test_get_invalid_json_raises() -> None:
    """Проверяет что невалидный JSON даёт ошибку"""
    cache, client = _cache()
    client.get.return_value = "not-json"
    try:
        await cache.get(1)
    except Exception:
        return
    raise AssertionError("ValidationError expected")


async def test_set_writes_json_with_ttl() -> None:
    """Проверяет запись в кэш с TTL"""
    cache, client = _cache(ttl=120)
    document = _doc(7)
    await cache.set(7, document)
    args, kwargs = client.set.call_args
    assert args[0] == "doc:7"
    assert kwargs["ex"] == 120
    assert DocumentOut.model_validate_json(args[1]) == document


async def test_invalidate_deletes_key() -> None:
    """Проверяет инвалидацию ключа"""
    cache, client = _cache()
    await cache.invalidate(5)
    client.delete.assert_awaited_once_with("doc:5")


async def test_invalidate_idempotent() -> None:
    """Проверяет что повторная инвалидация не падает"""
    cache, client = _cache()
    client.delete.return_value = 0
    await cache.invalidate(5)
    await cache.invalidate(5)
    assert client.delete.await_count == 2