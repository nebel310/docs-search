from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import EsClientDep, get_session_factory


router = APIRouter(tags=["health"])

SessionFactoryDep = Annotated[
    async_sessionmaker[AsyncSession],
    Depends(get_session_factory),
]


@router.get("/health")
async def health() -> dict[str, str]:
    """Возвращает liveness-статус сервиса"""
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    es_client: EsClientDep,
    factory: SessionFactoryDep,
    response: Response,
) -> dict[str, str | bool]:
    """Проверяет доступность PostgreSQL и Elasticsearch"""
    pg_ok = True
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        pg_ok = False

    es_ok = False
    try:
        es_ok = bool(await es_client.ping())
    except Exception:
        es_ok = False

    if not pg_ok or not es_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "pg": pg_ok, "es": es_ok}

    return {"status": "ok", "pg": pg_ok, "es": es_ok}