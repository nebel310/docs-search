import httpx


async def test_search_returns_results(api_client: httpx.AsyncClient) -> None:
    """Проверяет успешный поиск документов"""
    response = await api_client.get("/search", params={"q": "информации"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert len(body["items"]) > 0
    assert "id" in body["items"][0]
    assert "rubrics" in body["items"][0]
    assert "text" in body["items"][0]
    assert "created_date" in body["items"][0]


async def test_search_empty_query(api_client: httpx.AsyncClient) -> None:
    """Проверяет ошибку валидации при пустом запросе"""
    response = await api_client.get("/search", params={"q": ""})
    assert response.status_code == 422


async def test_search_missing_query(api_client: httpx.AsyncClient) -> None:
    """Проверяет ошибку при отсутствии параметра q"""
    response = await api_client.get("/search")
    assert response.status_code == 422


async def test_search_limit_boundary(api_client: httpx.AsyncClient) -> None:
    """Проверяет ошибку при превышении лимита выдачи"""
    response = await api_client.get("/search", params={"q": "test", "limit": 50})
    assert response.status_code == 422


async def test_search_no_results(api_client: httpx.AsyncClient) -> None:
    """Проверяет пустой результат поиска"""
    response = await api_client.get("/search", params={"q": "asdfghjklqwerty"})
    assert response.status_code == 200
    assert response.json()["total"] == 0