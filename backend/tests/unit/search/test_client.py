from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.search.client import create_es_client, ping


def test_create_es_client_passes_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что клиент создаётся с URL из настроек"""
    mock_cls = MagicMock()
    monkeypatch.setattr("app.search.client.AsyncElasticsearch", mock_cls)
    settings = Settings(_env_file=None, elasticsearch_url="http://es:9200")
    create_es_client(settings)
    mock_cls.assert_called_once_with(hosts=["http://es:9200"], request_timeout=5)


def test_create_es_client_returns_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что клиент возвращается"""
    mock_cls = MagicMock()
    monkeypatch.setattr("app.search.client.AsyncElasticsearch", mock_cls)
    settings = Settings(_env_file=None)
    client = create_es_client(settings)
    assert client is mock_cls.return_value


async def test_ping_true() -> None:
    """Проверяет ping возвращает True при доступном ES"""
    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    assert await ping(client) is True


async def test_ping_false() -> None:
    """Проверяет ping возвращает False при недоступном ES"""
    client = MagicMock()
    client.ping = AsyncMock(return_value=False)
    assert await ping(client) is False