import asyncio

import httpx


async def test_rate_limit_exceeded(api_client: httpx.AsyncClient) -> None:
    """Проверяет срабатывание rate limiter при частых запросах"""
    tasks = [api_client.get("/search", params={"q": "test"}) for _ in range(150)]
    responses = await asyncio.gather(*tasks)
    statuses = [response.status_code for response in responses]
    assert 429 in statuses