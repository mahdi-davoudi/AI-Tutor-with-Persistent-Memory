from fastapi import APIRouter, HTTPException, status

from core.exceptions import NotFoundError
from schemas.memory import UpsertMemoryRequest, MemoryResponse
from services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])

_service = MemoryService()


@router.post(
    "/{user_id}",
    response_model=MemoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Upsert a memory entry",
)
async def upsert_memory(
    user_id: str,
    body: UpsertMemoryRequest,
) -> MemoryResponse:
    return await _service.upsert(user_id=user_id, payload=body)


@router.get(
    "/{user_id}",
    response_model=list[MemoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List all memories for a user",
)
async def list_memories(
    user_id: str,
    min_importance: float = 0.0,
) -> list[MemoryResponse]:
    return await _service.list_memories(user_id=user_id, min_importance=min_importance)


@router.delete(
    "/{user_id}/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a specific memory",
)
async def delete_memory(user_id: str, memory_id: str) -> None:
    try:
        await _service.delete(user_id=user_id, memory_id=memory_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete all memories for a user",
)
async def delete_all_memories(user_id: str) -> dict:
    deleted = await _service.delete_all(user_id=user_id)
    return {"deleted": deleted}