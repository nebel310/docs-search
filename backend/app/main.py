import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routers import documents, health, search
from app.cache.document_cache import DocumentCache
from app.cache.redis_client import create_redis_client
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory
from app.rate_limit.middleware import RateLimitMiddleware
from app.search.client import create_es_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Инициализирует и освобождает ресурсы приложения"""
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    es_client: AsyncElasticsearch = create_es_client(settings)
    redis_client = create_redis_client(settings)
    cache = DocumentCache(redis_client, settings.cache_ttl_seconds)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.es_client = es_client
    app.state.redis = redis_client
    app.state.cache = cache
    app.state.clock = time.time
    try:
        yield
    finally:
        await redis_client.aclose()
        await es_client.close()
        await engine.dispose()


def create_app() -> FastAPI:
    """Создаёт и настраивает FastAPI-приложение"""
    application = FastAPI(title="Doc Search", version="0.1.0", lifespan=lifespan)
    application.add_middleware(RateLimitMiddleware)
    application.include_router(health.router)
    application.include_router(search.router)
    application.include_router(documents.router)

    @application.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        """Преобразует доменные исключения в JSON-ответ"""
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    return application


app = create_app()