from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "doc-search"
    app_env: str = "local"
    log_level: str = "INFO"

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "postgres"
    postgres_host: str = "pgbouncer"
    postgres_port: int = 6432

    database_url: str = "postgresql+asyncpg://postgres:postgres@pgbouncer:6432/postgres"

    elasticsearch_url: str = "http://elasticsearch:9200"
    elasticsearch_index: str = "documents"

    redis_url: str = "redis://redis:6379/0"

    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 1

    cache_ttl_seconds: int = 300
    search_candidates: int = 200
    search_result_limit: int = 20


@lru_cache
def get_settings() -> Settings:
    """Возвращает закешированный экземпляр настроек"""
    return Settings()