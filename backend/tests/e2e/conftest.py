import asyncio
import os
from collections.abc import AsyncIterator

import httpx
import pytest


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_RATE_WINDOW = 2.0


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Возвращает базовый URL запущенного сервиса"""
    return os.environ.get("E2E_BASE_URL", DEFAULT_BASE_URL)


@pytest.fixture(autouse=True)
async def _rate_limit_window_pause() -> AsyncIterator[None]:
    """Ждёт истечения окна rate limiter перед каждым e2e-тестом"""
    window = float(os.environ.get("E2E_RATE_LIMIT_WINDOW", DEFAULT_RATE_WINDOW))
    await asyncio.sleep(window)
    yield


@pytest.fixture
async def api_client(api_base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """Создаёт HTTP-клиент для e2e запросов"""
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        yield client