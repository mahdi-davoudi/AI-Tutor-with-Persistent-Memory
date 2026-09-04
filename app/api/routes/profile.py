from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.learning_profile import LearningProfileResponse
from app.services.profile_service import ProfileService
from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/{user_id}", response_model=LearningProfileResponse)
async def get_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> LearningProfileResponse:
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    try:
        return await ProfileService().get_profile(user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.post("/{user_id}/generate", response_model=LearningProfileResponse)
async def generate_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> LearningProfileResponse:
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    return await ProfileService().generate_profile(user_id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    try:
        await ProfileService().delete_profile(user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)