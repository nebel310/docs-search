from datetime import datetime, timedelta, timezone

from app.db.models import Document
from app.repositories.pg.document import DocumentRepository
from sqlalchemy import text


def _doc(doc_id: int | None = None, days_ago: int = 0) -> Document:
    """Создаёт ORM-документ с заданной давностью"""
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return Document(
        rubrics=["integration"],
        text=f"text-{doc_id}",
        created_date=created,
    )


async def test_migration_created_table(pg_session_factory) -> None:
    """Проверяет что миграция создала таблицу documents"""
    async with pg_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'documents' ORDER BY ordinal_position"
            )
        )
        columns = {row[0]: row[1] for row in result}
    assert set(columns.keys()) == {"id", "rubrics", "text", "created_date"}


async def test_create_and_get_by_id(pg_session_factory) -> None:
    """Проверяет вставку и чтение документа по id"""
    async with pg_session_factory() as session:
        repository = DocumentRepository(session)
        doc = _doc()
        session.add(doc)
        await session.commit()
        assert doc.id is not None
        loaded = await repository.get_by_id(doc.id)
        assert loaded is not None
        assert loaded.text == doc.text
        assert loaded.rubrics == ["integration"]


async def test_get_by_ids_empty_returns_empty(pg_session_factory) -> None:
    """Проверяет что пустой список id не даёт запросов"""
    async with pg_session_factory() as session:
        repository = DocumentRepository(session)
        assert await repository.get_by_ids([]) == []


async def test_get_by_ids_ordered_by_date_desc(pg_session_factory) -> None:
    """Проверяет сортировку по убыванию created_date"""
    async with pg_session_factory() as session:
        repository = DocumentRepository(session)
        old = _doc(1, days_ago=3)
        mid = _doc(2, days_ago=2)
        new = _doc(3, days_ago=1)
        session.add_all([old, mid, new])
        await session.commit()
        ids = [old.id, mid.id, new.id]
        documents = await repository.get_by_ids(ids)
        assert [d.id for d in documents] == [new.id, mid.id, old.id]


async def test_delete_existing(pg_session_factory) -> None:
    """Проверяет удаление существующего документа"""
    async with pg_session_factory() as session:
        repository = DocumentRepository(session)
        doc = _doc()
        session.add(doc)
        await session.commit()
        doc_id = doc.id
        assert await repository.delete(doc_id) is True
        await session.commit()
        assert await repository.get_by_id(doc_id) is None


async def test_delete_missing(pg_session_factory) -> None:
    """Проверяет что удаление отсутствующего возвращает False"""
    async with pg_session_factory() as session:
        repository = DocumentRepository(session)
        assert await repository.delete(9999) is False


async def test_truncate_between_tests(pg_session_factory) -> None:
    """Проверяет что fixture очищает таблицу между тестами"""
    async with pg_session_factory() as session:
        count = await session.execute(text("SELECT COUNT(*) FROM documents"))
        assert count.scalar() == 0