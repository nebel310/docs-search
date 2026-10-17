import argparse
import ast
import asyncio
import csv
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from elasticsearch import AsyncElasticsearch
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.models import Document
from app.db.session import create_engine, create_session_factory
from app.search.client import create_es_client
from app.search.index import bulk_index_documents, create_index, refresh_index


CHUNK_SIZE = 500
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_rubrics(raw: str) -> list[str]:
    """Парсит строку с Python-списком рубрик"""
    if not raw or not raw.strip():
        return []
    value = ast.literal_eval(raw.strip())
    if not isinstance(value, list):
        raise ValueError("rubrics must be a list")
    return [str(item) for item in value]


def parse_created_date(raw: str) -> datetime:
    """Парсит дату создания и привязывает UTC"""
    return datetime.strptime(raw.strip(), DATE_FORMAT).replace(tzinfo=timezone.utc)


def parse_row(row: dict[str, str]) -> dict[str, Any]:
    """Преобразует строку CSV в словарь для вставки"""
    return {
        "text": row["text"],
        "rubrics": parse_rubrics(row["rubrics"]),
        "created_date": parse_created_date(row["created_date"]),
    }


def read_csv(path: Path) -> Iterator[dict[str, Any]]:
    """Читает CSV построчно и отдаёт распарсенные документы"""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield parse_row(row)


def iter_chunks(items: Iterable[Any], size: int) -> Iterator[list[Any]]:
    """Разбивает итерируемое на чанки заданного размера"""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    chunk: list[Any] = []
    for item in items:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def build_documents(batch: list[dict[str, Any]]) -> list[Document]:
    """Строит ORM-документы из распарсенных строк"""
    return [Document(**row) for row in batch]


async def persist_batch(
    session_factory: async_sessionmaker[AsyncSession],
    es_client: AsyncElasticsearch,
    es_index: str,
    documents: list[Document],
) -> int:
    """Сохраняет пачку документов в PG и ES с откатом при ошибке ES"""
    async with session_factory() as session:
        session.add_all(documents)
        await session.flush()
        es_documents = [{"id": document.id, "text": document.text} for document in documents]
        try:
            await bulk_index_documents(es_client, es_index, es_documents, refresh=False)
        except Exception:
            await session.rollback()
            raise
        await session.commit()
    return len(es_documents)


async def run(
    csv_path: Path,
    settings: Settings | None = None,
    chunk_size: int = CHUNK_SIZE,
) -> int:
    """Запускает полный импорт CSV в PG и ES"""
    settings = settings or get_settings()
    logger = get_logger(__name__)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    es_client = create_es_client(settings)
    total = 0
    try:
        await create_index(es_client, settings.elasticsearch_index)
        for batch in iter_chunks(read_csv(csv_path), chunk_size):
            documents = build_documents(batch)
            count = await persist_batch(
                session_factory, es_client, settings.elasticsearch_index, documents
            )
            total += count
            logger.info("import_batch", count=count, total=total)
        await refresh_index(es_client, settings.elasticsearch_index)
    finally:
        await es_client.close()
        await engine.dispose()
    return total


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(description="Import CSV into PostgreSQL and Elasticsearch")
    parser.add_argument("--csv", type=Path, required=True, help="Path to CSV file")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="Batch size")
    return parser.parse_args()


async def main() -> None:
    """CLI-точка входа для импорта CSV"""
    args = parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    total = await run(args.csv, settings, args.chunk_size)
    get_logger(__name__).info("import_done", total=total)


if __name__ == "__main__":
    asyncio.run(main())