import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    """Проверяет дефолтные значения всех полей настроек"""
    settings = Settings(_env_file=None)
    assert settings.app_name == "doc-search"
    assert settings.app_env == "local"
    assert settings.log_level == "INFO"
    assert settings.postgres_host == "pgbouncer"
    assert settings.postgres_port == 6432
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.elasticsearch_index == "documents"
    assert settings.redis_url.startswith("redis://")
    assert settings.rate_limit_enabled is True
    assert settings.rate_limit_requests == 100
    assert settings.rate_limit_window_seconds == 1
    assert settings.cache_ttl_seconds == 300
    assert settings.search_candidates == 200
    assert settings.search_result_limit == 20


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет переопределение полей через переменные окружения"""
    monkeypatch.setenv("APP_NAME", "test-app")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("SEARCH_RESULT_LIMIT", "5")
    settings = Settings(_env_file=None)
    assert settings.app_name == "test-app"
    assert settings.app_env == "test"
    assert settings.postgres_port == 5432
    assert settings.rate_limit_enabled is False
    assert settings.search_result_limit == 5


def test_settings_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет регистронезависимость переменных окружения"""
    monkeypatch.setenv("app_name", "lowercase")
    settings = Settings(_env_file=None)
    assert settings.app_name == "lowercase"


def test_settings_extra_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет что неизвестные переменные окружения игнорируются"""
    monkeypatch.setenv("SOME_UNKNOWN_VAR", "value")
    settings = Settings(_env_file=None)
    assert settings.app_name == "doc-search"


def test_settings_invalid_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет ошибку валидации при невалидном типе поля"""
    monkeypatch.setenv("POSTGRES_PORT", "not-a-number")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_invalid_bool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет ошибку валидации при невалидном булевом значении"""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "not-a-bool")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_cached() -> None:
    """Проверяет что get_settings возвращает закешированный экземпляр"""
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second


def test_get_settings_returns_settings_instance() -> None:
    """Проверяет что get_settings возвращает экземпляр Settings"""
    get_settings.cache_clear()
    settings = get_settings()
    assert isinstance(settings, Settings)