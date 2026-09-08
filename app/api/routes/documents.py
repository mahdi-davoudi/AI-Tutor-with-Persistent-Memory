from app.models.user import User
from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status


router = APIRouter(prefix="/documents", tags=["documents"])

_service = DocumentService()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/{user_id}/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a document",
)
async def upload_document(
    user_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large (max 10MB)",
        )

    return await _service.ingest(
        user_id=user_id,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        raw=raw,
    )


@router.get(
    "/{user_id}",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List all documents for a user",
)
async def list_documents(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    return await _service.list_documents(user_id)


@router.delete(
    "/{user_id}/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a document and its vectors",
)
async def delete_document(
    user_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    try:
        await _service.delete(user_id=user_id, document_id=document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)

    return {"status": "deleted"}