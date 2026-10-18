from app.search.index import (
    bulk_index_documents,
    create_index,
    delete_document,
    delete_index,
    index_document,
    index_exists,
    refresh_index,
    search_documents,
)


async def test_create_index_idempotent(es_client) -> None:
    """Проверяет что повторный create_index не падает"""
    assert await index_exists(es_client, "documents_test") is True
    await create_index(es_client, "documents_test")


async def test_index_and_search(es_client) -> None:
    """Проверяет индексацию и поиск документа"""
    await index_document(es_client, "documents_test", 1, "hello python world")
    ids = await search_documents(es_client, "documents_test", "python", 10)
    assert ids == [1]


async def test_search_returns_empty_for_unknown(es_client) -> None:
    """Проверяет пустой результат для отсутствующего слова"""
    ids = await search_documents(es_client, "documents_test", "zzz", 10)
    assert ids == []


async def test_bulk_index(es_client) -> None:
    """Проверяет bulk-индексацию и поиск"""
    docs = [{"id": 1, "text": "one"}, {"id": 2, "text": "two three"}]
    count = await bulk_index_documents(es_client, "documents_test", docs)
    assert count == 2
    await refresh_index(es_client, "documents_test")
    ids = await search_documents(es_client, "documents_test", "three", 10)
    assert ids == [2]


async def test_delete_document(es_client) -> None:
    """Проверяет удаление документа из индекса"""
    await index_document(es_client, "documents_test", 1, "delete me")
    await delete_document(es_client, "documents_test", 1)
    ids = await search_documents(es_client, "documents_test", "delete", 10)
    assert ids == []


async def test_delete_missing_document_does_not_raise(es_client) -> None:
    """Проверяет что удаление отсутствующего документа не падает"""
    await delete_document(es_client, "documents_test", 9999)


async def test_delete_index(es_client) -> None:
    """Проверяет удаление индекса"""
    await delete_index(es_client, "documents_test")
    assert await index_exists(es_client, "documents_test") is False