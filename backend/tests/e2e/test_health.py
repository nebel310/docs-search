import httpx


async def test_health(api_client: httpx.AsyncClient) -> None:
    """Проверяет liveness-эндпоинт"""
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_ready(api_client: httpx.AsyncClient) -> None:
    """Проверяет readiness-эндпоинт"""
    response = await api_client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["pg"] is True
    assert body["es"] is True