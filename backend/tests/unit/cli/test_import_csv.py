from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cli.import_csv import (
    build_documents,
    iter_chunks,
    parse_created_date,
    parse_row,
    parse_rubrics,
    persist_batch,
    read_csv,
    run,
)
from app.core.config import Settings
from app.db.models import Document


def test_parse_rubrics_valid() -> None:
    """Парсит список рубрик"""
    assert parse_rubrics("['a', 'b']") == ["a", "b"]


def test_parse_rubrics_empty_string() -> None:
    """Возвращает пустой список для пустой строки"""
    assert parse_rubrics("") == []


def test_parse_rubrics_whitespace_only() -> None:
    """Возвращает пустой список для строки из пробелов"""
    assert parse_rubrics("   ") == []


def test_parse_rubrics_empty_list() -> None:
    """Парсит пустой список"""
    assert parse_rubrics("[]") == []


def test_parse_rubrics_single_item() -> None:
    """Парсит список из одного элемента"""
    assert parse_rubrics("['x']") == ["x"]


def test_parse_rubrics_converts_to_str() -> None:
    """Приводит элементы к строкам"""
    assert parse_rubrics("[1, 2]") == ["1", "2"]


def test_parse_rubrics_not_a_list_raises() -> None:
    """Падает если значение не список"""
    with pytest.raises(ValueError):
        parse_rubrics("'not-a-list'")


def test_parse_rubrics_invalid_syntax_raises() -> None:
    """Падает при синтаксической ошибке"""
    with pytest.raises(SyntaxError):
        parse_rubrics("[")


def test_parse_created_date_valid() -> None:
    """Парсит дату и привязывает UTC"""
    result = parse_created_date("2019-07-25 12:42:13")
    assert result == datetime(2019, 7, 25, 12, 42, 13, tzinfo=timezone.utc)
    assert result.tzinfo is timezone.utc


def test_parse_created_date_with_whitespace() -> None:
    """Обрезает пробелы вокруг даты"""
    assert parse_created_date("  2019-07-25 12:42:13  ") == datetime(
        2019, 7, 25, 12, 42, 13, tzinfo=timezone.utc
    )


def test_parse_created_date_invalid_raises() -> None:
    """Падает при невалидном формате"""
    with pytest.raises(ValueError):
        parse_created_date("not-a-date")


def test_parse_row_combines_fields() -> None:
    """Собирает строку в словарь"""
    row = {
        "text": "hello",
        "created_date": "2020-01-01 00:00:00",
        "rubrics": "['a']",
    }
    result = parse_row(row)
    assert result["text"] == "hello"
    assert result["rubrics"] == ["a"]
    assert result["created_date"] == datetime(2020, 1, 1, tzinfo=timezone.utc)


def test_iter_chunks_even_split() -> None:
    """Делит на равные чанки"""
    assert list(iter_chunks([1, 2, 3, 4], 2)) == [[1, 2], [3, 4]]


def test_iter_chunks_with_remainder() -> None:
    """Оставляет неполный чанк в конце"""
    assert list(iter_chunks([1, 2, 3], 2)) == [[1, 2], [3]]


def test_iter_chunks_empty() -> None:
    """Пустой вход даёт пустой список"""
    assert list(iter_chunks([], 3)) == []


def test_iter_chunks_size_larger_than_input() -> None:
    """Чанк больше входа содержит всё"""
    assert list(iter_chunks([1, 2], 10)) == [[1, 2]]


def test_iter_chunks_zero_size_raises() -> None:
    """Размер 0 недопустим"""
    with pytest.raises(ValueError):
        list(iter_chunks([1], 0))


def test_iter_chunks_negative_size_raises() -> None:
    """Отрицательный размер недопустим"""
    with pytest.raises(ValueError):
        list(iter_chunks([1], -1))


def test_read_csv_yields_parsed_rows(tmp_path: Path) -> None:
    """Читает CSV и отдаёт распарсенные документы"""
    path = tmp_path / "posts.csv"
    path.write_text(
        'text,created_date,rubrics\n"hello","2020-01-01 00:00:00","[\'a\', \'b\']"\n',
        encoding="utf-8",
    )
    rows = list(read_csv(path))
    assert len(rows) == 1
    assert rows[0]["text"] == "hello"
    assert rows[0]["rubrics"] == ["a", "b"]
    assert rows[0]["created_date"] == datetime(2020, 1, 1, tzinfo=timezone.utc)


def test_read_csv_empty_file(tmp_path: Path) -> None:
    """CSV только с заголовком не даёт строк"""
    path = tmp_path / "empty.csv"
    path.write_text("text,created_date,rubrics\n", encoding="utf-8")
    assert list(read_csv(path)) == []


def test_build_documents() -> None:
    """Строит ORM-документы из словарей"""
    batch = [
        {"text": "a", "rubrics": ["x"], "created_date": datetime.now(timezone.utc)},
        {"text": "b", "rubrics": [], "created_date": datetime.now(timezone.utc)},
    ]
    documents = build_documents(batch)
    assert len(documents) == 2
    assert all(isinstance(doc, Document) for doc in documents)
    assert documents[0].text == "a"
    assert documents[1].rubrics == []


async def test_persist_batch_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет успешное сохранение пачки"""
    session = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    session_factory = MagicMock(return_value=cm)
    es_client = MagicMock()
    bulk = AsyncMock(return_value=2)
    monkeypatch.setattr("app.cli.import_csv.bulk_index_documents", bulk)
    documents = [
        Document(id=1, rubrics=[], text="a", created_date=datetime.now(timezone.utc)),
        Document(id=2, rubrics=[], text="b", created_date=datetime.now(timezone.utc)),
    ]
    count = await persist_batch(session_factory, es_client, "documents", documents)
    assert count == 2
    session.add_all.assert_called_once_with(documents)
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    bulk.assert_awaited_once_with(
        es_client,
        "documents",
        [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}],
        refresh=False,
    )


async def test_persist_batch_rollback_on_es_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет откат при ошибке ES"""
    session = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    session_factory = MagicMock(return_value=cm)
    es_client = MagicMock()
    bulk = AsyncMock(side_effect=RuntimeError("es down"))
    monkeypatch.setattr("app.cli.import_csv.bulk_index_documents", bulk)
    documents = [
        Document(id=1, rubrics=[], text="a", created_date=datetime.now(timezone.utc)),
    ]
    with pytest.raises(RuntimeError):
        await persist_batch(session_factory, es_client, "documents", documents)
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


async def test_persist_batch_empty_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Пустая пачка возвращает 0"""
    session = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    session_factory = MagicMock(return_value=cm)
    bulk = AsyncMock(return_value=0)
    monkeypatch.setattr("app.cli.import_csv.bulk_index_documents", bulk)
    assert await persist_batch(session_factory, MagicMock(), "documents", []) == 0


async def test_run_full_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Проверяет полный пайплайн импорта"""
    path = tmp_path / "posts.csv"
    path.write_text(
        'text,created_date,rubrics\n"a","2020-01-01 00:00:00","[\'x\']"\n'
        '"b","2020-01-02 00:00:00","[\'y\']"\n',
        encoding="utf-8",
    )
    engine = MagicMock()
    engine.dispose = AsyncMock()
    es_client = MagicMock()
    es_client.close = AsyncMock()
    persist = AsyncMock(return_value=2)
    refresh = AsyncMock()
    create = AsyncMock()
    monkeypatch.setattr("app.cli.import_csv.create_engine", MagicMock(return_value=engine))
    monkeypatch.setattr(
        "app.cli.import_csv.create_session_factory", MagicMock(return_value=MagicMock())
    )
    monkeypatch.setattr("app.cli.import_csv.create_es_client", MagicMock(return_value=es_client))
    monkeypatch.setattr("app.cli.import_csv.persist_batch", persist)
    monkeypatch.setattr("app.cli.import_csv.refresh_index", refresh)
    monkeypatch.setattr("app.cli.import_csv.create_index", create)
    settings = Settings(_env_file=None)
    total = await run(path, settings, chunk_size=10)
    assert total == 2
    create.assert_awaited_once()
    persist.assert_awaited_once()
    refresh.assert_awaited_once()
    es_client.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()


async def test_run_closes_resources_on_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Проверяет освобождение ресурсов при ошибке"""
    path = tmp_path / "posts.csv"
    path.write_text("text,created_date,rubrics\n", encoding="utf-8")
    engine = MagicMock()
    engine.dispose = AsyncMock()
    es_client = MagicMock()
    es_client.close = AsyncMock()
    create = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr("app.cli.import_csv.create_engine", MagicMock(return_value=engine))
    monkeypatch.setattr(
        "app.cli.import_csv.create_session_factory", MagicMock(return_value=MagicMock())
    )
    monkeypatch.setattr("app.cli.import_csv.create_es_client", MagicMock(return_value=es_client))
    monkeypatch.setattr("app.cli.import_csv.create_index", create)
    settings = Settings(_env_file=None)
    with pytest.raises(RuntimeError):
        await run(path, settings)
    es_client.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()