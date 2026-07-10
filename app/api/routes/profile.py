from fastapi import APIRouter, HTTPException, status
from app.schemas.learning_profile import LearningProfileResponse
from app.services.profile_service import ProfileService
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/{user_id}", response_model=LearningProfileResponse)
async def get_profile(user_id: str) -> LearningProfileResponse:
    try:
        return await ProfileService().get_profile(user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.post("/{user_id}/generate", response_model=LearningProfileResponse)
async def generate_profile(user_id: str) -> LearningProfileResponse:
    return await ProfileService().generate_profile(user_id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(user_id: str) -> None:
    try:
        await ProfileService().delete_profile(user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)