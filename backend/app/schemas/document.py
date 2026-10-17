from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    """Документ в ответе API"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный id документа")
    rubrics: list[str] = Field(..., description="Список рубрик документа")
    text: str = Field(..., description="Текст документа")
    created_date: datetime = Field(..., description="Дата создания документа")