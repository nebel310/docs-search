from typing import Any

from elasticsearch import AsyncElasticsearch

from app.core.exceptions import SearchUnavailableError


DOCUMENTS_INDEX_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "text": {"type": "text"},
        }
    }
}


async def index_exists(client: AsyncElasticsearch, index: str) -> bool:
    """Проверяет существование индекса"""
    return bool(await client.indices.exists(index=index))


async def create_index(client: AsyncElasticsearch, index: str) -> None:
    """Создаёт индекс с маппингом если он ещё не существует"""
    if await index_exists(client, index):
        return
    await client.indices.create(index=index, mappings=DOCUMENTS_INDEX_MAPPING["mappings"])


async def delete_index(client: AsyncElasticsearch, index: str) -> None:
    """Удаляет индекс если он существует"""
    if not await index_exists(client, index):
        return
    await client.indices.delete(index=index)


async def index_document(client: AsyncElasticsearch, index: str, doc_id: int, text: str) -> None:
    """Индексирует один документ с ожиданием refresh"""
    await client.index(
        index=index,
        id=str(doc_id),
        document={"id": doc_id, "text": text},
        refresh="wait_for",
    )


async def bulk_index_documents(
    client: AsyncElasticsearch,
    index: str,
    documents: list[dict[str, Any]],
) -> int:
    """Индексирует пачку документов через bulk и возвращает их количество"""
    if not documents:
        return 0
    operations: list[dict[str, Any]] = []
    for document in documents:
        operations.append({"index": {"_index": index, "_id": str(document["id"])}})
        operations.append({"id": document["id"], "text": document["text"]})
    response = await client.bulk(operations=operations, refresh="wait_for")
    if response.get("errors"):
        raise SearchUnavailableError("Bulk indexing failed")
    return len(documents)


async def delete_document(client: AsyncElasticsearch, index: str, doc_id: int) -> None:
    """Удаляет документ из индекса игнорируя отсутствие"""
    await client.delete(index=index, id=str(doc_id), refresh="wait_for", ignore_status=[404])


async def search_documents(
    client: AsyncElasticsearch,
    index: str,
    query: str,
    size: int,
) -> list[int]:
    """Ищет документы по тексту и возвращает список id"""
    response = await client.search(
        index=index,
        query={"match": {"text": query}},
        size=size,
        source=False,
    )
    return [int(hit["_id"]) for hit in response["hits"]["hits"]]