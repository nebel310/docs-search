from collections.abc import Iterator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_search_service
from app.db.models import Document
from app.main import create_app
from app.services.search_service import SearchService


def _doc(doc_id: int) -> Document:
    """Создаёт тестовый документ"""
    return Document(
        id=doc_id,
        rubrics=["x"],
        text="t",
        created_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def app_with_service() -> Iterator[tuple[FastAPI, MagicMock]]:
    """Создаёт приложение с моком SearchService"""
    application = create_app()
    service = MagicMock(spec=SearchService)
    service.search = AsyncMock(return_value=[_doc(1), _doc(2)])
    application.dependency_overrides[get_search_service] = lambda: service
    yield application, service
    application.dependency_overrides.clear()


async def test_search_ok(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет успешный поиск"""
    application, _ = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/search", params={"q": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [1, 2]


async def test_search_empty_query_422(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет ошибку валидации при пустом q"""
    application, _ = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/search", params={"q": ""})
    assert response.status_code == 422


async def test_search_missing_query_422(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет ошибку при отсутствии q"""
    application, _ = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/search")
    assert response.status_code == 422


async def test_search_query_too_long_422(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет ошибку при слишком длинном q"""
    application, _ = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/search", params={"q": "a" * 501})
    assert response.status_code == 422


async def test_search_limit_boundary_low(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет limit=1"""
    application, _ = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/search", params={"q": "hello", "limit": 1})
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_search_limit_boundary_high(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет limit=20"""
    application, _ = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/search", params={"q": "hello", "limit": 20})
    assert response.status_code == 200


async def test_search_limit_zero_422(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет ошибку при limit=0"""
    application, _ = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/search", params={"q": "hello", "limit": 0})
    assert response.status_code == 422


async def test_search_limit_exceeds_422(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет ошибку при limit > 20"""
    application, _ = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/search", params={"q": "hello", "limit": 21})
    assert response.status_code == 422


async def test_search_empty_result(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет пустой результат поиска"""
    application, service = app_with_service
    service.search = AsyncMock(return_value=[])
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/search", params={"q": "hello"})
    assert response.status_code == 200
    assert response.json() == {"total": 0, "items": []}


async def test_search_passes_query_to_service(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет что q передаётся в сервис"""
    application, service = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        await client.get("/search", params={"q": "python"})
    service.search.assert_awaited_once_with("python")