from pydantic import BaseModel, Field

from app.schemas.document import DocumentOut


QUERY_MIN_LENGTH = 1
QUERY_MAX_LENGTH = 500
LIMIT_MAX = 20
LIMIT_DEFAULT = 20


class SearchRequest(BaseModel):
    """Параметры поискового запроса"""

    q: str = Field(
        ...,
        min_length=QUERY_MIN_LENGTH,
        max_length=QUERY_MAX_LENGTH,
        description="Текстовый поисковый запрос",
    )
    limit: int = Field(
        LIMIT_DEFAULT,
        ge=1,
        le=LIMIT_MAX,
        description="Максимальное количество результатов",
    )


class SearchResponse(BaseModel):
    """Результат поиска"""

    total: int = Field(..., description="Количество возвращённых документов")
    items: list[DocumentOut] = Field(..., description="Список найденных документов")