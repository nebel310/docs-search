from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.config import Settings
from app.rate_limit.middleware import SKIP_PATHS, RateLimitMiddleware


def _app(redis: MagicMock | None, enabled: bool = True) -> FastAPI:
    """Создаёт приложение с middleware и заглушкой роута"""
    application = FastAPI()
    application.add_middleware(RateLimitMiddleware)
    application.state.settings = Settings(
        _env_file=None,
        rate_limit_enabled=enabled,
        rate_limit_requests=2,
        rate_limit_window_seconds=1,
    )
    application.state.redis = redis
    application.state.clock = lambda: 1000.0

    @application.get("/ping")
    async def ping() -> dict[str, str]:
        """Заглушка роута"""
        return {"ok": "yes"}

    return application


async def _stub_endpoint(_: Request) -> JSONResponse:
    """Заглушка эндпоинта для skip-путей"""
    return JSONResponse({"ok": "yes"})


@pytest.fixture
def redis_allow() -> Iterator[MagicMock]:
    """Мок Redis, всегда разрешающий запрос"""
    client = MagicMock()
    client.eval = AsyncMock(return_value=1)
    yield client


@pytest.fixture
def redis_deny() -> Iterator[MagicMock]:
    """Мок Redis, всегда отклоняющий запрос"""
    client = MagicMock()
    client.eval = AsyncMock(return_value=0)
    yield client


async def test_disabled_passes_through() -> None:
    """Проверяет что при выключенном лимитере запрос проходит"""
    application = _app(redis=None, enabled=False)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://t") as client:
        response = await client.get("/ping")
    assert response.status_code == 200


async def test_no_redis_passes_through() -> None:
    """Проверяет fail-open при отсутствии Redis"""
    application = _app(redis=None, enabled=True)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://t") as client:
        response = await client.get("/ping")
    assert response.status_code == 200


async def test_allowed_request(redis_allow: MagicMock) -> None:
    """Проверяет что разрешённый запрос проходит"""
    application = _app(redis=redis_allow)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://t") as client:
        response = await client.get("/ping")
    assert response.status_code == 200


async def test_exceeded_returns_429(redis_deny: MagicMock) -> None:
    """Проверяет 429 при превышении лимита"""
    application = _app(redis=redis_deny)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://t") as client:
        response = await client.get("/ping")
    assert response.status_code == 429
    body = response.json()
    assert body["error"]["code"] == "rate_limit_exceeded"
    assert "Retry-After" in response.headers


async def test_eval_error_fail_open() -> None:
    """Проверяет fail-open при ошибке Redis"""
    client = MagicMock()
    client.eval = AsyncMock(side_effect=RuntimeError("boom"))
    application = _app(redis=client)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://t") as http:
        response = await http.get("/ping")
    assert response.status_code == 200


async def test_skip_paths_do_not_evaluate(redis_deny: MagicMock) -> None:
    """Проверяет что skip-пути не трогают Redis"""
    application = _app(redis=redis_deny)
    for path in SKIP_PATHS:
        application.router.routes.append(
            Route(path=path, endpoint=_stub_endpoint, methods=["GET"])
        )
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://t") as http:
        for path in SKIP_PATHS:
            response = await http.get(path)
            assert response.status_code == 200
    redis_deny.eval.assert_not_awaited()


async def test_key_includes_host_and_path(redis_allow: MagicMock) -> None:
    """Проверяет что ключ включает host и path"""
    application = _app(redis=redis_allow)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://t") as http:
        await http.get("/ping")
    args = redis_allow.eval.call_args.args
    key = args[2]
    assert key.startswith("rl:")
    assert key.endswith("/ping")