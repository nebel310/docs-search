from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document


class DocumentRepository:
    """Репозиторий документов в PostgreSQL"""

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию для выполнения запросов"""
        self._session = session

    async def get_by_id(self, doc_id: int) -> Document | None:
        """Возвращает документ по id или None"""
        result = await self._session.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def get_by_ids(self, doc_ids: list[int]) -> list[Document]:
        """Возвращает документы по списку id упорядоченные по дате создания"""
        if not doc_ids:
            return []
        stmt = (
            select(Document)
            .where(Document.id.in_(doc_ids))
            .order_by(Document.created_date.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, doc_id: int) -> bool:
        """Удаляет документ по id и возвращает признак успеха"""
        result = await self._session.execute(delete(Document).where(Document.id == doc_id))
        return result.rowcount > 0