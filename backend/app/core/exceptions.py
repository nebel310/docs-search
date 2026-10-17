class AppError(Exception):
    """Базовое исключение приложения"""

    status_code: int = 500
    code: str = "internal_error"
    default_message: str = "Internal server error"

    def __init__(self, message: str | None = None) -> None:
        """Инициализирует исключение с опциональным сообщением"""
        self.message = message or self.default_message
        super().__init__(self.message)


class DocumentNotFoundError(AppError):
    """Документ с указанным id не найден"""

    status_code = 404
    code = "document_not_found"
    default_message = "Document not found"


class SearchUnavailableError(AppError):
    """Поисковый индекс недоступен"""

    status_code = 503
    code = "search_unavailable"
    default_message = "Search is temporarily unavailable"


class RateLimitExceededError(AppError):
    """Превышен лимит запросов"""

    status_code = 429
    code = "rate_limit_exceeded"
    default_message = "Too many requests"