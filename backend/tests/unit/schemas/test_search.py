import pytest
from pydantic import ValidationError

from app.schemas.search import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    QUERY_MAX_LENGTH,
    QUERY_MIN_LENGTH,
    SearchRequest,
    SearchResponse,
)


def test_search_request_default_limit() -> None:
    """Проверяет дефолтное значение limit"""
    request = SearchRequest(q="hello")
    assert request.limit == LIMIT_DEFAULT


def test_search_request_custom_limit() -> None:
    """Проверяет кастомный limit в допустимых границах"""
    request = SearchRequest(q="hello", limit=5)
    assert request.limit == 5


def test_search_request_limit_max_boundary() -> None:
    """Проверяет граничное значение limit сверху"""
    request = SearchRequest(q="hello", limit=LIMIT_MAX)
    assert request.limit == LIMIT_MAX


def test_search_request_limit_below_one_raises() -> None:
    """Проверяет ошибку при limit < 1"""
    with pytest.raises(ValidationError):
        SearchRequest(q="hello", limit=0)


def test_search_request_limit_above_max_raises() -> None:
    """Проверяет ошибку при limit > LIMIT_MAX"""
    with pytest.raises(ValidationError):
        SearchRequest(q="hello", limit=LIMIT_MAX + 1)


def test_search_request_empty_query_raises() -> None:
    """Проверяет ошибку при пустом q"""
    with pytest.raises(ValidationError):
        SearchRequest(q="")


def test_search_request_query_min_length_boundary() -> None:
    """Проверяет минимально допустимый q"""
    request = SearchRequest(q="a")
    assert len(request.q) == QUERY_MIN_LENGTH


def test_search_request_query_max_length_boundary() -> None:
    """Проверяет максимально допустимый q"""
    request = SearchRequest(q="a" * QUERY_MAX_LENGTH)
    assert len(request.q) == QUERY_MAX_LENGTH


def test_search_request_query_too_long_raises() -> None:
    """Проверяет ошибку при q длиннее лимита"""
    with pytest.raises(ValidationError):
        SearchRequest(q="a" * (QUERY_MAX_LENGTH + 1))


def test_search_request_unicode_query() -> None:
    """Проверяет что unicode-запрос проходит валидацию"""
    request = SearchRequest(q="привет мир")
    assert request.q == "привет мир"


def test_search_request_whitespace_query_allowed() -> None:
    """Проверяет что строка из пробелов проходит как непустая"""
    request = SearchRequest(q="   ")
    assert request.q == "   "


def test_search_response_empty_items() -> None:
    """Проверяет пустой ответ поиска"""
    response = SearchResponse(total=0, items=[])
    assert response.total == 0
    assert response.items == []


def test_search_response_with_items() -> None:
    """Проверяет ответ с документами"""
    payload = {
        "id": 1,
        "rubrics": ["a"],
        "text": "hello",
        "created_date": "2024-01-01T00:00:00Z",
    }
    response = SearchResponse(total=1, items=[payload])
    assert response.total == 1
    assert response.items[0].id == 1


def test_search_response_invalid_item_raises() -> None:
    """Проверяет ошибку при невалидном документе в items"""
    with pytest.raises(ValidationError):
        SearchResponse(total=1, items=[{"id": 1}])