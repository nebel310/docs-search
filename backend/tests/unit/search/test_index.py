from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import SearchUnavailableError
from app.search.index import (
    DOCUMENTS_INDEX_MAPPING,
    bulk_index_documents,
    create_index,
    delete_document,
    delete_index,
    index_document,
    index_exists,
    refresh_index,
    search_documents,
)


def _client() -> MagicMock:
    """Создаёт мок ES-клиента с async-методами"""
    client = MagicMock()
    client.indices = MagicMock()
    client.indices.exists = AsyncMock()
    client.indices.create = AsyncMock()
    client.indices.delete = AsyncMock()
    client.indices.refresh = AsyncMock()
    client.index = AsyncMock()
    client.bulk = AsyncMock()
    client.delete = AsyncMock()
    client.search = AsyncMock()
    return client


def test_mapping_structure() -> None:
    """Проверяет маппинг индекса"""
    props = DOCUMENTS_INDEX_MAPPING["mappings"]["properties"]
    assert props["id"] == {"type": "keyword"}
    assert props["text"] == {"type": "text"}
    assert set(props.keys()) == {"id", "text"}


async def test_index_exists_true() -> None:
    """Проверяет что index_exists возвращает True"""
    client = _client()
    client.indices.exists.return_value = True
    assert await index_exists(client, "documents") is True
    client.indices.exists.assert_awaited_once_with(index="documents")


async def test_index_exists_false() -> None:
    """Проверяет что index_exists возвращает False"""
    client = _client()
    client.indices.exists.return_value = False
    assert await index_exists(client, "documents") is False


async def test_create_index_when_missing() -> None:
    """Проверяет создание индекса если его нет"""
    client = _client()
    client.indices.exists.return_value = False
    await create_index(client, "documents")
    client.indices.create.assert_awaited_once_with(
        index="documents",
        mappings=DOCUMENTS_INDEX_MAPPING["mappings"],
    )


async def test_create_index_when_exists_skips() -> None:
    """Проверяет что индекс не пересоздаётся если уже есть"""
    client = _client()
    client.indices.exists.return_value = True
    await create_index(client, "documents")
    client.indices.create.assert_not_awaited()


async def test_delete_index_when_exists() -> None:
    """Проверяет удаление существующего индекса"""
    client = _client()
    client.indices.exists.return_value = True
    await delete_index(client, "documents")
    client.indices.delete.assert_awaited_once_with(index="documents")


async def test_delete_index_when_missing_skips() -> None:
    """Проверяет что удаление отсутствующего индекса не вызывает ES"""
    client = _client()
    client.indices.exists.return_value = False
    await delete_index(client, "documents")
    client.indices.delete.assert_not_awaited()


async def test_index_document_calls_es_with_refresh() -> None:
    """Проверяет индексацию одного документа"""
    client = _client()
    await index_document(client, "documents", 42, "hello")
    client.index.assert_awaited_once_with(
        index="documents",
        id="42",
        document={"id": 42, "text": "hello"},
        refresh="wait_for",
    )


async def test_bulk_index_documents_empty_returns_zero() -> None:
    """Проверяет что пустой список не обращается к ES"""
    client = _client()
    assert await bulk_index_documents(client, "documents", []) == 0
    client.bulk.assert_not_awaited()


async def test_bulk_index_documents_success() -> None:
    """Проверяет успешный bulk и возврат количества"""
    client = _client()
    client.bulk.return_value = {"errors": False}
    docs = [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}]
    assert await bulk_index_documents(client, "documents", docs) == 2
    client.bulk.assert_awaited_once()


async def test_bulk_index_documents_default_refresh() -> None:
    """Проверяет что по умолчанию используется wait_for"""
    client = _client()
    client.bulk.return_value = {"errors": False}
    await bulk_index_documents(client, "documents", [{"id": 1, "text": "x"}])
    assert client.bulk.call_args.kwargs["refresh"] == "wait_for"


async def test_bulk_index_documents_custom_refresh_false() -> None:
    """Проверяет что refresh=False прокидывается в ES"""
    client = _client()
    client.bulk.return_value = {"errors": False}
    await bulk_index_documents(client, "documents", [{"id": 1, "text": "x"}], refresh=False)
    assert client.bulk.call_args.kwargs["refresh"] is False


async def test_bulk_index_documents_operations_format() -> None:
    """Проверяет формат операций для bulk"""
    client = _client()
    client.bulk.return_value = {"errors": False}
    await bulk_index_documents(client, "documents", [{"id": 7, "text": "x"}])
    operations = client.bulk.call_args.kwargs["operations"]
    assert operations == [
        {"index": {"_index": "documents", "_id": "7"}},
        {"id": 7, "text": "x"},
    ]


async def test_bulk_index_documents_errors_raises() -> None:
    """Проверяет что errors=True приводит к SearchUnavailableError"""
    client = _client()
    client.bulk.return_value = {"errors": True}
    with pytest.raises(SearchUnavailableError):
        await bulk_index_documents(client, "documents", [{"id": 1, "text": "x"}])


async def test_refresh_index_calls_es() -> None:
    """Проверяет что refresh_index вызывает indices.refresh"""
    client = _client()
    await refresh_index(client, "documents")
    client.indices.refresh.assert_awaited_once_with(index="documents")


async def test_delete_document_ignores_404() -> None:
    """Проверяет что удаление вызывает ES с ignore_status 404"""
    client = _client()
    await delete_document(client, "documents", 10)
    client.delete.assert_awaited_once_with(
        index="documents",
        id="10",
        refresh="wait_for",
        ignore_status=[404],
    )


async def test_search_documents_returns_ids() -> None:
    """Проверяет что search_documents возвращает список id"""
    client = _client()
    client.search.return_value = {"hits": {"hits": [{"_id": "1"}, {"_id": "2"}]}}
    ids = await search_documents(client, "documents", "hello", 50)
    assert ids == [1, 2]


async def test_search_documents_empty_hits() -> None:
    """Проверяет что пустой hits даёт пустой список"""
    client = _client()
    client.search.return_value = {"hits": {"hits": []}}
    assert await search_documents(client, "documents", "nope", 50) == []


async def test_search_documents_passes_query_and_size() -> None:
    """Проверяет что query, size и source корректно передаются"""
    client = _client()
    client.search.return_value = {"hits": {"hits": []}}
    await search_documents(client, "documents", "python", 200)
    client.search.assert_awaited_once_with(
        index="documents",
        query={"match": {"text": "python"}},
        size=200,
        source=False,
    )