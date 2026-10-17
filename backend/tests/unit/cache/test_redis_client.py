from unittest.mock import MagicMock

import pytest

from app.cache.redis_client import create_redis_client
from app.core.config import Settings


def test_create_redis_client_uses_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что клиент создаётся с URL из настроек"""
    mock_from_url = MagicMock()
    monkeypatch.setattr("app.cache.redis_client.Redis.from_url", mock_from_url)
    settings = Settings(_env_file=None, redis_url="redis://cache:6379/1")
    create_redis_client(settings)
    mock_from_url.assert_called_once_with("redis://cache:6379/1", decode_responses=True)


def test_create_redis_client_returns_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что клиент возвращается"""
    mock_from_url = MagicMock()
    monkeypatch.setattr("app.cache.redis_client.Redis.from_url", mock_from_url)
    client = create_redis_client(Settings(_env_file=None))
    assert client is mock_from_url.return_value