import httpx


async def _first_doc_id(api_client: httpx.AsyncClient) -> int:
    """Достаёт id первого документа из поисковой выдачи"""
    response = await api_client.get("/search", params={"q": "информации"})
    items = response.json()["items"]
    assert items
    return items[0]["id"]


async def test_get_existing_document(api_client: httpx.AsyncClient) -> None:
    """Проверяет получение существующего документа"""
    doc_id = await _first_doc_id(api_client)
    response = await api_client.get(f"/documents/{doc_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == doc_id


async def test_get_missing_document(api_client: httpx.AsyncClient) -> None:
    """Проверяет 404 при отсутствии документа"""
    response = await api_client.get("/documents/999999999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "document_not_found"


async def test_delete_and_verify(api_client: httpx.AsyncClient) -> None:
    """Проверяет удаление документа и его отсутствие после этого"""
    doc_id = await _first_doc_id(api_client)
    delete_response = await api_client.delete(f"/documents/{doc_id}")
    assert delete_response.status_code == 204
    get_response = await api_client.get(f"/documents/{doc_id}")
    assert get_response.status_code == 404