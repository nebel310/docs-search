from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.db.models import Document
from app.repositories.pg.document import DocumentRepository


def _session() -> MagicMock:
    """Создаёт мок AsyncSession с async execute"""
    session = MagicMock()
    session.execute = AsyncMock()
    return session


def _result_scalar(value: object) -> MagicMock:
    """Создаёт мок Result с scalar_one_or_none"""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


def _result_scalars(values: list[Document]) -> MagicMock:
    """Создаёт мок Result с scalars().all()"""
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=values)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    return result


def _doc(doc_id: int, text: str = "t") -> Document:
    """Создаёт тестовый документ с текущей датой"""
    return Document(id=doc_id, rubrics=[], text=text, created_date=datetime.now(timezone.utc))


async def test_get_by_id_returns_document() -> None:
    """Проверяет что get_by_id возвращает найденный документ"""
    session = _session()
    doc = _doc(1)
    session.execute.return_value = _result_scalar(doc)
    repository = DocumentRepository(session)
    assert await repository.get_by_id(1) is doc
    session.execute.assert_awaited_once()


async def test_get_by_id_not_found_returns_none() -> None:
    """Проверяет что get_by_id возвращает None если документа нет"""
    session = _session()
    session.execute.return_value = _result_scalar(None)
    repository = DocumentRepository(session)
    assert await repository.get_by_id(999) is None


async def test_get_by_ids_empty_returns_empty_without_query() -> None:
    """Проверяет что пустой список id не ходит в БД"""
    session = _session()
    repository = DocumentRepository(session)
    assert await repository.get_by_ids([]) == []
    session.execute.assert_not_awaited()


async def test_get_by_ids_returns_documents() -> None:
    """Проверяет что get_by_ids возвращает документы"""
    session = _session()
    docs = [_doc(1), _doc(2)]
    session.execute.return_value = _result_scalars(docs)
    repository = DocumentRepository(session)
    assert await repository.get_by_ids([1, 2]) == docs
    session.execute.assert_awaited_once()


async def test_get_by_ids_single_query_for_duplicates() -> None:
    """Проверяет что дубликаты в id не приводят к повторным запросам"""
    session = _session()
    session.execute.return_value = _result_scalars([])
    repository = DocumentRepository(session)
    await repository.get_by_ids([1, 1, 1])
    session.execute.assert_awaited_once()


async def test_get_by_ids_ordered_by_created_date_desc() -> None:
    """Проверяет что в SQL присутствует сортировка по created_date desc"""
    session = _session()
    session.execute.return_value = _result_scalars([])
    repository = DocumentRepository(session)
    await repository.get_by_ids([1, 2])
    statement = session.execute.call_args.args[0]
    sql = str(statement)
    assert "ORDER BY documents.created_date DESC" in sql


async def test_get_by_ids_uses_in_clause() -> None:
    """Проверяет что для списка id используется IN"""
    session = _session()
    session.execute.return_value = _result_scalars([])
    repository = DocumentRepository(session)
    await repository.get_by_ids([1, 2, 3])
    statement = session.execute.call_args.args[0]
    assert "IN" in str(statement)


async def test_delete_existing_returns_true() -> None:
    """Проверяет что удаление существующего документа возвращает True"""
    session = _session()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result
    repository = DocumentRepository(session)
    assert await repository.delete(1) is True
    session.execute.assert_awaited_once()


async def test_delete_missing_returns_false() -> None:
    """Проверяет что удаление отсутствующего документа возвращает False"""
    session = _session()
    result = MagicMock()
    result.rowcount = 0
    session.execute.return_value = result
    repository = DocumentRepository(session)
    assert await repository.delete(999) is False


async def test_delete_emits_delete_statement() -> None:
    """Проверяет что delete формирует SQL DELETE"""
    session = _session()
    result = MagicMock()
    result.rowcount = 0
    session.execute.return_value = result
    repository = DocumentRepository(session)
    await repository.delete(5)
    statement = session.execute.call_args.args[0]
    assert str(statement).startswith("DELETE FROM documents")