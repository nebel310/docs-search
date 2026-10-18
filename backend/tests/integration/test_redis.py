from datetime import datetime, timezone

import pytest

from app.cache.document_cache import DocumentCache
from app.rate_limit.script import SLIDING_WINDOW_SCRIPT
from app.schemas.document import DocumentOut


def _doc(doc_id: int = 1) -> DocumentOut:
    """Создаёт тестовый DocumentOut"""
    return DocumentOut(
        id=doc_id,
        rubrics=["redis"],
        text="cached",
        created_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


async def test_cache_miss(redis_client) -> None:
    """Проверяет промах кэша"""
    cache = DocumentCache(redis_client, ttl_seconds=10)
    assert await cache.get(1) is None


async def test_cache_set_and_get(redis_client) -> None:
    """Проверяет запись и чтение из кэша"""
    cache = DocumentCache(redis_client, ttl_seconds=10)
    doc = _doc(1)
    await cache.set(1, doc)
    loaded = await cache.get(1)
    assert loaded == doc


async def test_cache_invalidate(redis_client) -> None:
    """Проверяет инвалидацию кэша"""
    cache = DocumentCache(redis_client, ttl_seconds=10)
    await cache.set(1, _doc(1))
    await cache.invalidate(1)
    assert await cache.get(1) is None


async def test_cache_ttl_expires(redis_client) -> None:
    """Проверяет что TTL применяется к ключу"""
    cache = DocumentCache(redis_client, ttl_seconds=1)
    await cache.set(1, _doc(1))
    ttl = await redis_client.ttl("doc:1")
    assert ttl > 0


async def test_rate_limiter_allows_first_requests(redis_client) -> None:
    """Проверяет что первые запросы пропускаются"""
    for i in range(3):
        allowed = await redis_client.eval(
            SLIDING_WINDOW_SCRIPT, 1, "rl:test:/search", 1000 + i, 60000, 5, f"m{i}"
        )
        assert allowed == 1


async def test_rate_limiter_blocks_after_limit(redis_client) -> None:
    """Проверяет что после лимита приходит отказ"""
    for i in range(5):
        await redis_client.eval(
            SLIDING_WINDOW_SCRIPT, 1, "rl:test:/search", 2000, 60000, 5, f"m{i}"
        )
    blocked = await redis_client.eval(
        SLIDING_WINDOW_SCRIPT, 1, "rl:test:/search", 2000, 60000, 5, "overflow"
    )
    assert blocked == 0


async def test_rate_limiter_window_slides(redis_client) -> None:
    """Проверяет что старые записи выпадают из окна"""
    for i in range(5):
        await redis_client.eval(
            SLIDING_WINDOW_SCRIPT, 1, "rl:test:/search", 3000, 1000, 5, f"m{i}"
        )
    blocked = await redis_client.eval(
        SLIDING_WINDOW_SCRIPT, 1, "rl:test:/search", 3000, 1000, 5, "now"
    )
    assert blocked == 0
    allowed = await redis_client.eval(
        SLIDING_WINDOW_SCRIPT, 1, "rl:test:/search", 5000, 1000, 5, "later"
    )
    assert allowed == 1