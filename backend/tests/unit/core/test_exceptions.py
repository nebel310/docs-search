import pytest

from app.core.exceptions import (
    AppError,
    DocumentNotFoundError,
    RateLimitExceededError,
    SearchUnavailableError,
)


def test_app_error_default_message() -> None:
    """Проверяет дефолтное сообщение базового исключения"""
    error = AppError()
    assert error.message == "Internal server error"
    assert str(error) == "Internal server error"
    assert error.status_code == 500
    assert error.code == "internal_error"


def test_app_error_custom_message() -> None:
    """Проверяет кастомное сообщение базового исключения"""
    error = AppError("Boom")
    assert error.message == "Boom"
    assert str(error) == "Boom"


def test_app_error_empty_message_falls_back() -> None:
    """Проверяет что пустое сообщение заменяется дефолтным"""
    error = AppError("")
    assert error.message == "Internal server error"


def test_document_not_found_defaults() -> None:
    """Проверяет параметры DocumentNotFoundError"""
    error = DocumentNotFoundError()
    assert error.status_code == 404
    assert error.code == "document_not_found"
    assert error.message == "Document not found"


def test_document_not_found_custom_message() -> None:
    """Проверяет кастомное сообщение DocumentNotFoundError"""
    error = DocumentNotFoundError("Doc 42 missing")
    assert error.message == "Doc 42 missing"
    assert str(error) == "Doc 42 missing"


def test_search_unavailable_defaults() -> None:
    """Проверяет параметры SearchUnavailableError"""
    error = SearchUnavailableError()
    assert error.status_code == 503
    assert error.code == "search_unavailable"
    assert error.message == "Search is temporarily unavailable"


def test_rate_limit_exceeded_defaults() -> None:
    """Проверяет параметры RateLimitExceededError"""
    error = RateLimitExceededError()
    assert error.status_code == 429
    assert error.code == "rate_limit_exceeded"
    assert error.message == "Too many requests"


@pytest.mark.parametrize(
    "exc_class",
    [DocumentNotFoundError, SearchUnavailableError, RateLimitExceededError],
)
def test_subclasses_are_app_errors(exc_class: type[AppError]) -> None:
    """Проверяет наследование всех доменных исключений от AppError"""
    assert issubclass(exc_class, AppError)
    instance = exc_class()
    assert isinstance(instance, AppError)