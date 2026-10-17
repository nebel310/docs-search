from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import DocumentNotFoundError
from app.services.document_service import DocumentCacheProtocol, DocumentService


def _service(
    deleted: bool,
    cache: DocumentCacheProtocol | None = None,
    es_error: Exception | None = None,
) -> tuple[DocumentService, MagicMock, MagicMock]:
    """Создаёт сервис с моками репозиториев и кэша"""
    document_repository = MagicMock()
    document_repository.delete = AsyncMock(return_value=deleted)
    search_repository = MagicMock()
    if es_error is not None:
        search_repository.delete = AsyncMock(side_effect=es_error)
    else:
        search_repository.delete = AsyncMock()
    service = DocumentService(document_repository, search_repository, cache)
    return service, document_repository, search_repository


async def test_delete_existing_document() -> None:
    """Проверяет успешное удаление существующего документа"""
    cache = MagicMock()
    cache.invalidate = AsyncMock()
    service, document_repository, search_repository = _service(True, cache)
    await service.delete(1)
    document_repository.delete.assert_awaited_once_with(1)
    search_repository.delete.assert_awaited_once_with(1)
    cache.invalidate.assert_awaited_once_with(1)


async def test_delete_not_found_raises() -> None:
    """Проверяет что удаление отсутствующего документа даёт 404"""
    service, _, search_repository = _service(False)
    with pytest.raises(DocumentNotFoundError):
        await service.delete(999)
    search_repository.delete.assert_not_awaited()


async def test_delete_without_cache() -> None:
    """Проверяет что cache=None не ломает удаление"""
    service, _, search_repository = _service(True, cache=None)
    await service.delete(1)
    search_repository.delete.assert_awaited_once_with(1)


async def test_delete_pg_before_es() -> None:
    """Проверяет что PG вызывается раньше ES"""
    call_order: list[str] = []
    document_repository = MagicMock()
    search_repository = MagicMock()

    async def pg_delete(_: int) -> bool:
        call_order.append("pg")
        return True

    async def es_delete(_: int) -> None:
        call_order.append("es")

    document_repository.delete = pg_delete
    search_repository.delete = es_delete
    service = DocumentService(document_repository, search_repository)
    await service.delete(1)
    assert call_order == ["pg", "es"]


async def test_delete_es_failure_does_not_raise() -> None:
    """Проверяет что падение ES не ломает удаление"""
    cache = MagicMock()
    cache.invalidate = AsyncMock()
    service, _, _ = _service(True, cache, es_error=RuntimeError("es down"))
    await service.delete(1)
    cache.invalidate.assert_awaited_once_with(1)


async def test_delete_cache_invalidated_before_es() -> None:
    """Проверяет что кэш инвалидируется до вызова ES"""
    call_order: list[str] = []
    document_repository = MagicMock()
    document_repository.delete = AsyncMock(return_value=True)
    cache = MagicMock()

    async def invalidate(_: int) -> None:
        call_order.append("cache")

    async def es_delete(_: int) -> None:
        call_order.append("es")

    cache.invalidate = invalidate
    search_repository = MagicMock()
    search_repository.delete = es_delete
    service = DocumentService(document_repository, search_repository, cache)
    await service.delete(1)
    assert call_order == ["cache", "es"]


async def test_delete_es_not_called_when_not_found() -> None:
    """Проверяет что ES не вызывается если PG не нашёл документ"""
    service, _, search_repository = _service(False)
    with pytest.raises(DocumentNotFoundError):
        await service.delete(42)
    search_repository.delete.assert_not_awaited()


async def test_delete_es_error_is_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что ошибка ES пишется в лог"""
    warning = MagicMock()
    monkeypatch.setattr("app.services.document_service.logger.warning", warning)
    service, _, _ = _service(True, es_error=RuntimeError("boom"))
    await service.delete(7)
    warning.assert_called_once()
    args, kwargs = warning.call_args
    assert args[0] == "es_delete_failed"
    assert kwargs["doc_id"] == 7
    assert "boom" in kwargs["error"]