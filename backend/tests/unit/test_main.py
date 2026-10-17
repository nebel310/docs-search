from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from app.core.exceptions import AppError
from app.main import create_app, lifespan
from app.rate_limit.middleware import RateLimitMiddleware


def _patch_resources(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Подменяет фабрики ресурсов и возвращает моки"""
    engine = MagicMock()
    engine.dispose = AsyncMock()
    es_client = MagicMock()
    es_client.close = AsyncMock()
    redis_client = MagicMock()
    redis_client.aclose = AsyncMock()
    monkeypatch.setattr("app.main.create_engine", MagicMock(return_value=engine))
    monkeypatch.setattr("app.main.create_session_factory", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr("app.main.create_es_client", MagicMock(return_value=es_client))
    monkeypatch.setattr("app.main.create_redis_client", MagicMock(return_value=redis_client))
    monkeypatch.setattr("app.main.configure_logging", MagicMock())
    return engine, es_client, redis_client


async def test_lifespan_creates_and_closes_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет создание и освобождение ресурсов в lifespan"""
    engine, es_client, redis_client = _patch_resources(monkeypatch)
    app = FastAPI()
    async with lifespan(app):
        assert app.state.engine is engine
        assert app.state.es_client is es_client
        assert app.state.redis is redis_client
        assert app.state.cache is not None
        assert app.state.session_factory is not None
        assert app.state.clock is not None
    redis_client.aclose.assert_awaited_once()
    es_client.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()


async def test_lifespan_closes_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет освобождение ресурсов при исключении"""
    engine, es_client, redis_client = _patch_resources(monkeypatch)
    app = FastAPI()
    with pytest.raises(RuntimeError):
        async with lifespan(app):
            raise RuntimeError("boom")
    redis_client.aclose.assert_awaited_once()
    es_client.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()


def test_create_app_registers_routes() -> None:
    """Проверяет что create_app регистрирует все роуты"""
    application = create_app()
    paths = {route.path for route in application.routes}
    assert "/health" in paths
    assert "/ready" in paths
    assert "/search" in paths
    assert "/documents/{doc_id}" in paths


def test_create_app_registers_rate_limit_middleware() -> None:
    """Проверяет что middleware rate limiter зарегистрирован"""
    application = create_app()
    middleware_classes = [m.cls for m in application.user_middleware]
    assert RateLimitMiddleware in middleware_classes


def test_create_app_registers_app_error_handler() -> None:
    """Проверяет что обработчик AppError зарегистрирован"""
    application = create_app()
    assert AppError in application.exception_handlers