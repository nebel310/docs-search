import argparse
import asyncio

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.search.client import create_es_client
from app.search.index import create_index, delete_index


async def run(settings: Settings | None = None, drop: bool = False) -> None:
    """Создаёт индекс документов и опционально пересоздаёт его"""
    settings = settings or get_settings()
    es_client = create_es_client(settings)
    try:
        if drop:
            await delete_index(es_client, settings.elasticsearch_index)
        await create_index(es_client, settings.elasticsearch_index)
    finally:
        await es_client.close()


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(description="Initialize Elasticsearch index")
    parser.add_argument("--drop", action="store_true", help="Drop index before creation")
    return parser.parse_args()


async def main() -> None:
    """CLI-точка входа для инициализации ES"""
    args = parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    await run(settings, args.drop)
    get_logger(__name__).info("es_initialized", drop=args.drop)


if __name__ == "__main__":
    asyncio.run(main())