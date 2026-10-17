from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.core.exceptions import SearchUnavailableError
from app.db.models import Document
from app.services.search_service import SearchService


def _settings() -> Settings:
    """Создаёт настройки с фиксированными лимитами"""
    return Settings(_env_file=None, search_candidates=200, search_result_limit=20)


def _doc(doc_id: int) -> Document:
    """Создаёт тестовый документ"""
    return Document(
        id=doc_id,
        rubrics=[],
        text=f"doc-{doc_id}",
        created_date=datetime.now(timezone.utc),
    )


def _service(
    search_ids: list[int] | Exception,
    docs: list[Document] | Exception,
    settings: Settings | None = None,
) -> tuple[SearchService, MagicMock, MagicMock]:
    """Создаёт сервис с моками репозиториев"""
    search_repository = MagicMock()
    document_repository = MagicMock()
    if isinstance(search_ids, Exception):
        search_repository.search = AsyncMock(side_effect=search_ids)
    else:
        search_repository.search = AsyncMock(return_value=search_ids)
    if isinstance(docs, Exception):
        document_repository.get_by_ids = AsyncMock(side_effect=docs)
    else:
        document_repository.get_by_ids = AsyncMock(return_value=docs)
    service = SearchService(search_repository, document_repository, settings or _settings())
    return service, search_repository, document_repository


async def test_search_returns_documents() -> None:
    """Проверяет что search возвращает документы из PG"""
    docs = [_doc(1), _doc(2)]
    service, _, _ = _service([1, 2], docs)
    assert await service.search("hello") == docs


async def test_search_empty_es_result_returns_empty() -> None:
    """Проверяет что пустой результат ES даёт пустой список"""
    service, _, document_repository = _service([], [])
    assert await service.search("nope") == []
    document_repository.get_by_ids.assert_not_awaited()


async def test_search_passes_candidates_to_es() -> None:
    """Проверяет что в ES передаётся search_candidates"""
    settings = _settings()
    service, search_repository, _ = _service([1], [_doc(1)], settings)
    await service.search("q")
    search_repository.search.assert_awaited_once_with("q", settings.search_candidates)


async def test_search_respects_result_limit() -> None:
    """Проверяет обрезку результата до search_result_limit"""
    settings = Settings(_env_file=None, search_candidates=200, search_result_limit=2)
    docs = [_doc(i) for i in range(5)]
    service, _, _ = _service([1, 2, 3, 4, 5], docs, settings)
    result = await service.search("q")
    assert len(result) == 2
    assert result == docs[:2]


async def test_search_returns_fewer_when_pg_missing() -> None:
    """Проверяет что при рассинхроне возвращаются только найденные в PG"""
    service, _, _ = _service([1, 2, 3], [_doc(1)])
    result = await service.search("q")
    assert [d.id for d in result] == [1]


async def test_search_propagates_es_error() -> None:
    """Проверяет что ошибка ES пробрасывается наружу"""
    service, _, _ = _service(SearchUnavailableError(), [])
    with pytest.raises(SearchUnavailableError):
        await service.search("q")


async def test_search_preserves_pg_order() -> None:
    """Проверяет что порядок документов из PG сохраняется"""
    docs = [_doc(3), _doc(1), _doc(2)]
    service, _, _ = _service([1, 2, 3], docs)
    result = await service.search("q")
    assert [d.id for d in result] == [3, 1, 2]


async def test_search_no_es_call_when_limit_zero() -> None:
    """Проверяет что лимит 0 всё равно сначала вызывает ES"""
    settings = Settings(_env_file=None, search_candidates=200, search_result_limit=0)
    service, search_repository, _ = _service([1], [_doc(1)], settings)
    assert await service.search("q") == []
    search_repository.search.assert_awaited_once()