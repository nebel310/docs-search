from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_document_service
from app.core.exceptions import AppError, DocumentNotFoundError
from app.main import create_app
from app.services.document_service import DocumentService


@pytest.fixture
def app_with_service() -> Iterator[tuple[FastAPI, MagicMock]]:
    """Создаёт приложение с моком DocumentService"""
    application = create_app()
    service = MagicMock(spec=DocumentService)
    service.delete = AsyncMock()
    application.dependency_overrides[get_document_service] = lambda: service
    yield application, service
    application.dependency_overrides.clear()


async def test_delete_ok(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет успешное удаление"""
    application, service = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.delete("/documents/1")
    assert response.status_code == 204
    assert response.content == b""
    service.delete.assert_awaited_once_with(1)


async def test_delete_not_found_404(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет 404 при отсутствии документа"""
    application, service = app_with_service
    service.delete = AsyncMock(side_effect=DocumentNotFoundError())
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.delete("/documents/999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "document_not_found"
    assert body["error"]["message"] == "Document not found"


async def test_delete_invalid_id_422(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет ошибку валидации при невалидном id"""
    application, _ = app_with_service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.delete("/documents/abc")
    assert response.status_code == 422


async def test_delete_app_error_500(app_with_service: tuple[FastAPI, MagicMock]) -> None:
    """Проверяет маппинг базового AppError в 500"""
    application, service = app_with_service
    service.delete = AsyncMock(side_effect=AppError("boom"))
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.delete("/documents/1")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "boom"