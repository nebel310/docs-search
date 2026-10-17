from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from app.main import lifespan


async def test_lifespan_creates_and_closes_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет создание и освобождение ресурсов в lifespan"""
    engine = MagicMock()
    engine.dispose = AsyncMock()
    session_factory = MagicMock()
    es_client = MagicMock()
    es_client.close = AsyncMock()

    monkeypatch.setattr("app.main.create_engine", MagicMock(return_value=engine))
    monkeypatch.setattr("app.main.create_session_factory", MagicMock(return_value=session_factory))
    monkeypatch.setattr("app.main.create_es_client", MagicMock(return_value=es_client))
    monkeypatch.setattr("app.main.configure_logging", MagicMock())

    app = FastAPI()

    async with lifespan(app):
        assert app.state.engine is engine
        assert app.state.session_factory is session_factory
        assert app.state.es_client is es_client
        assert app.state.cache is None

    es_client.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()


async def test_lifespan_closes_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет освобождение ресурсов при исключении"""
    engine = MagicMock()
    engine.dispose = AsyncMock()
    es_client = MagicMock()
    es_client.close = AsyncMock()

    monkeypatch.setattr("app.main.create_engine", MagicMock(return_value=engine))
    monkeypatch.setattr("app.main.create_session_factory", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr("app.main.create_es_client", MagicMock(return_value=es_client))
    monkeypatch.setattr("app.main.configure_logging", MagicMock())

    app = FastAPI()
    with pytest.raises(RuntimeError):
        async with lifespan(app):
            raise RuntimeError("boom")

    es_client.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()


def test_create_app_registers_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что create_app регистрирует все роуты"""
    from app.main import create_app

    monkeypatch.setattr("app.main.lifespan", MagicMock())
    application = create_app()
    paths = {route.path for route in application.routes}
    assert "/health" in paths
    assert "/ready" in paths
    assert "/search" in paths
    assert "/documents/{doc_id}" in paths


def test_create_app_registers_app_error_handler() -> None:
    """Проверяет что обработчик AppError зарегистрирован"""
    from app.core.exceptions import AppError
    from app.main import create_app

    application = create_app()
    assert AppError in application.exception_handlers