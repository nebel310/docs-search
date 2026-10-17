from fastapi import APIRouter, Response, status

from app.api.deps import DocumentServiceDep


router = APIRouter(prefix="/documents", tags=["documents"])


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: int, service: DocumentServiceDep) -> Response:
    """Удаляет документ по id"""
    await service.delete(doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)