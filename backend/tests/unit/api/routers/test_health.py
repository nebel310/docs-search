from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_es_client, get_session_factory
from app.main import create_app


@pytest.fixture
def app_with_mocks() -> Iterator[tuple[FastAPI, MagicMock, MagicMock]]:
    """Создаёт приложение с моками PG и ES"""
    application = create_app()
    es_client = MagicMock(spec=AsyncElasticsearch)
    es_client.ping = AsyncMock(return_value=True)
    factory = MagicMock(spec=async_sessionmaker)
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    factory.return_value = cm
    application.dependency_overrides[get_es_client] = lambda: es_client
    application.dependency_overrides[get_session_factory] = lambda: factory
    yield application, es_client, factory
    application.dependency_overrides.clear()


async def test_health_returns_ok(app_with_mocks: tuple[FastAPI, MagicMock, MagicMock]) -> None:
    """Проверяет liveness-эндпоинт"""
    application, _, _ = app_with_mocks
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_ok(app_with_mocks: tuple[FastAPI, MagicMock, MagicMock]) -> None:
    """Проверяет ready при доступных PG и ES"""
    application, _, _ = app_with_mocks
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["pg"] is True
    assert body["es"] is True


async def test_ready_pg_down(app_with_mocks: tuple[FastAPI, MagicMock, MagicMock]) -> None:
    """Проверяет ready при недоступном PG"""
    application, _, factory = app_with_mocks
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(side_effect=RuntimeError("pg down"))
    cm.__aexit__ = AsyncMock(return_value=None)
    factory.return_value = cm
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["pg"] is False
    assert body["es"] is True


async def test_ready_es_down(app_with_mocks: tuple[FastAPI, MagicMock, MagicMock]) -> None:
    """Проверяет ready при недоступном ES"""
    application, es_client, _ = app_with_mocks
    es_client.ping = AsyncMock(return_value=False)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["es"] is False


async def test_ready_es_error(app_with_mocks: tuple[FastAPI, MagicMock, MagicMock]) -> None:
    """Проверяет ready при ошибке ES"""
    application, es_client, _ = app_with_mocks
    es_client.ping = AsyncMock(side_effect=RuntimeError("boom"))
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503


async def test_ready_both_down(app_with_mocks: tuple[FastAPI, MagicMock, MagicMock]) -> None:
    """Проверяет ready при недоступных PG и ES"""
    application, es_client, factory = app_with_mocks
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(side_effect=RuntimeError("pg down"))
    cm.__aexit__ = AsyncMock(return_value=None)
    factory.return_value = cm
    es_client.ping = AsyncMock(return_value=False)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["pg"] is False
    assert body["es"] is False