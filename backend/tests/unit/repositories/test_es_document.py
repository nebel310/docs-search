from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.es.document import SearchRepository


def _client() -> MagicMock:
    """Создаёт мок Elasticsearch-клиента"""
    return MagicMock()


async def test_search_delegates_to_search_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что search делегирует в search_documents"""
    mock = AsyncMock(return_value=[1, 2])
    monkeypatch.setattr("app.repositories.es.document.search_documents", mock)
    client = _client()
    repository = SearchRepository(client, "documents")
    assert await repository.search("q", 50) == [1, 2]
    mock.assert_awaited_once_with(client, "documents", "q", 50)


async def test_search_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что search возвращает пустой список"""
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr("app.repositories.es.document.search_documents", mock)
    repository = SearchRepository(_client(), "documents")
    assert await repository.search("nope", 50) == []


async def test_index_delegates_to_index_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что index делегирует в index_document"""
    mock = AsyncMock()
    monkeypatch.setattr("app.repositories.es.document.index_document", mock)
    client = _client()
    repository = SearchRepository(client, "documents")
    await repository.index(7, "hello")
    mock.assert_awaited_once_with(client, "documents", 7, "hello")


async def test_bulk_index_delegates_to_bulk_index_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет что bulk_index делегирует и возвращает счётчик"""
    mock = AsyncMock(return_value=3)
    monkeypatch.setattr("app.repositories.es.document.bulk_index_documents", mock)
    client = _client()
    repository = SearchRepository(client, "documents")
    documents = [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}, {"id": 3, "text": "c"}]
    assert await repository.bulk_index(documents) == 3
    mock.assert_awaited_once_with(client, "documents", documents)


async def test_bulk_index_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что bulk_index с пустым списком возвращает 0"""
    mock = AsyncMock(return_value=0)
    monkeypatch.setattr("app.repositories.es.document.bulk_index_documents", mock)
    repository = SearchRepository(_client(), "documents")
    assert await repository.bulk_index([]) == 0


async def test_delete_delegates_to_delete_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что delete делегирует в delete_document"""
    mock = AsyncMock()
    monkeypatch.setattr("app.repositories.es.document.delete_document", mock)
    client = _client()
    repository = SearchRepository(client, "documents")
    await repository.delete(5)
    mock.assert_awaited_once_with(client, "documents", 5)