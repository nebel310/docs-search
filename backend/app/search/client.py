from elasticsearch import AsyncElasticsearch

from app.core.config import Settings


REQUEST_TIMEOUT_SECONDS = 5


def create_es_client(settings: Settings) -> AsyncElasticsearch:
    """Создаёт асинхронный клиент Elasticsearch"""
    return AsyncElasticsearch(hosts=[settings.elasticsearch_url], request_timeout=REQUEST_TIMEOUT_SECONDS)


async def ping(client: AsyncElasticsearch) -> bool:
    """Проверяет доступность Elasticsearch"""
    return await client.ping()