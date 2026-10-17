from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import DocumentNotFoundError
from app.db.models import Document
from app.schemas.document import DocumentOut
from app.services.document_service import DocumentService


def _doc(doc_id: int = 1) -> Document:
    """Создаёт тестовый ORM-документ"""
    return Document(
        id=doc_id,
        rubrics=["a"],
        text="t",
        created_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _schema(doc_id: int = 1, text: str = "t") -> DocumentOut:
    """Создаёт тестовую схему документа"""
    return DocumentOut(
        id=doc_id,
        rubrics=["a"],
        text=text,
        created_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _build(
    pg_doc: Document | None = None,
    deleted: bool | None = None,
    cache_hit: DocumentOut | None = None,
    cache_present: bool = True,
    es_error: Exception | None = None,
) -> tuple[DocumentService, MagicMock, MagicMock, MagicMock | None]:
    """Собирает сервис с моками репозиториев и кэша"""
    document_repository = MagicMock()
    document_repository.get_by_id = AsyncMock(return_value=pg_doc)
    if deleted is None:
        document_repository.delete = AsyncMock(return_value=pg_doc is not None)
    else:
        document_repository.delete = AsyncMock(return_value=deleted)

    search_repository = MagicMock()
    if es_error is not None:
        search_repository.delete = AsyncMock(side_effect=es_error)
    else:
        search_repository.delete = AsyncMock()

    cache = None
    if cache_present:
        cache = MagicMock()
        cache.get = AsyncMock(return_value=cache_hit)
        cache.set = AsyncMock()
        cache.invalidate = AsyncMock()

    service = DocumentService(document_repository, search_repository, cache)
    return service, document_repository, search_repository, cache


async def test_delete_existing_document() -> None:
    """Проверяет успешное удаление существующего документа"""
    service, document_repository, search_repository, cache = _build(pg_doc=_doc(1), deleted=True)
    await service.delete(1)
    document_repository.delete.assert_awaited_once_with(1)
    search_repository.delete.assert_awaited_once_with(1)
    assert cache is not None
    cache.invalidate.assert_awaited_once_with(1)


async def test_delete_not_found_raises() -> None:
    """Проверяет что удаление отсутствующего документа даёт 404"""
    service, _, search_repository, _ = _build(deleted=False)
    with pytest.raises(DocumentNotFoundError):
        await service.delete(999)
    search_repository.delete.assert_not_awaited()


async def test_delete_without_cache() -> None:
    """Проверяет что cache=None не ломает удаление"""
    service, _, search_repository, cache = _build(
        pg_doc=_doc(1), deleted=True, cache_present=False
    )
    await service.delete(1)
    assert cache is None
    search_repository.delete.assert_awaited_once_with(1)


async def test_delete_pg_before_es() -> None:
    """Проверяет что PG вызывается раньше ES"""
    call_order: list[str] = []
    document_repository = MagicMock()
    search_repository = MagicMock()

    async def pg_delete(_: int) -> bool:
        """Заглушка удаления в PG"""
        call_order.append("pg")
        return True

    async def es_delete(_: int) -> None:
        """Заглушка удаления в ES"""
        call_order.append("es")

    document_repository.delete = pg_delete
    search_repository.delete = es_delete
    service = DocumentService(document_repository, search_repository)
    await service.delete(1)
    assert call_order == ["pg", "es"]


async def test_delete_es_failure_does_not_raise() -> None:
    """Проверяет что падение ES не ломает удаление"""
    service, _, _, cache = _build(pg_doc=_doc(1), deleted=True, es_error=RuntimeError("es down"))
    await service.delete(1)
    assert cache is not None
    cache.invalidate.assert_awaited_once_with(1)


async def test_delete_cache_invalidated_before_es() -> None:
    """Проверяет что кэш инвалидируется до вызова ES"""
    call_order: list[str] = []
    document_repository = MagicMock()
    document_repository.delete = AsyncMock(return_value=True)
    cache = MagicMock()

    async def invalidate(_: int) -> None:
        """Заглушка инвалидации кэша"""
        call_order.append("cache")

    async def es_delete(_: int) -> None:
        """Заглушка удаления в ES"""
        call_order.append("es")

    cache.invalidate = invalidate
    search_repository = MagicMock()
    search_repository.delete = es_delete
    service = DocumentService(document_repository, search_repository, cache)
    await service.delete(1)
    assert call_order == ["cache", "es"]


async def test_delete_es_not_called_when_not_found() -> None:
    """Проверяет что ES не вызывается если PG не нашёл документ"""
    service, _, search_repository, _ = _build(deleted=False)
    with pytest.raises(DocumentNotFoundError):
        await service.delete(42)
    search_repository.delete.assert_not_awaited()


async def test_delete_es_error_is_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что ошибка ES пишется в лог"""
    warning = MagicMock()
    monkeypatch.setattr("app.services.document_service.logger.warning", warning)
    service, _, _, _ = _build(pg_doc=_doc(7), deleted=True, es_error=RuntimeError("boom"))
    await service.delete(7)
    warning.assert_called_once()
    args, kwargs = warning.call_args
    assert args[0] == "es_delete_failed"
    assert kwargs["doc_id"] == 7
    assert "boom" in kwargs["error"]


async def test_get_cache_hit() -> None:
    """Проверяет что get возвращает документ из кэша"""
    cached = _schema(1, "cached")
    service, pg, _, _ = _build(pg_doc=None, cache_hit=cached)
    assert await service.get(1) == cached
    pg.get_by_id.assert_not_awaited()


async def test_get_cache_miss_reads_pg_and_sets_cache() -> None:
    """Проверяет что get читает PG и пишет в кэш"""
    service, pg, _, cache = _build(pg_doc=_doc(1), cache_hit=None)
    result = await service.get(1)
    assert result.id == 1
    pg.get_by_id.assert_awaited_once_with(1)
    assert cache is not None
    cache.set.assert_awaited_once()


async def test_get_not_found_raises() -> None:
    """Проверяет 404 при отсутствии документа"""
    service, _, _, _ = _build(pg_doc=None, cache_hit=None)
    with pytest.raises(DocumentNotFoundError):
        await service.get(42)


async def test_get_without_cache() -> None:
    """Проверяет работу get без кэша"""
    service, pg, _, _ = _build(pg_doc=_doc(1), cache_present=False)
    result = await service.get(1)
    assert result.id == 1
    pg.get_by_id.assert_awaited_once_with(1)