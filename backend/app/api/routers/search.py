from fastapi import APIRouter, Query

from app.api.deps import SearchServiceDep
from app.schemas.document import DocumentOut
from app.schemas.search import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    QUERY_MAX_LENGTH,
    QUERY_MIN_LENGTH,
    SearchResponse,
)


router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    service: SearchServiceDep,
    q: str = Query(
        ...,
        min_length=QUERY_MIN_LENGTH,
        max_length=QUERY_MAX_LENGTH,
        description="Текстовый поисковый запрос",
    ),
    limit: int = Query(
        LIMIT_DEFAULT,
        ge=1,
        le=LIMIT_MAX,
        description="Максимальное количество результатов",
    ),
) -> SearchResponse:
    """Ищет документы по тексту и возвращает топ-N по дате создания"""
    documents = await service.search(q)
    items = [DocumentOut.model_validate(document) for document in documents[:limit]]
    return SearchResponse(total=len(items), items=items)