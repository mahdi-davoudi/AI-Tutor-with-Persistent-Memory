from fastapi import APIRouter, Depends, HTTPException, status
from app.services.recommendation_service import RecommendationService
from app.schemas.recommendation import RecommendationResponse, RecommendationRequest
from app.core.security import get_current_user
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def get_recommendation_service() -> RecommendationService:
    return RecommendationService()


@router.get("/{user_id}", response_model=RecommendationResponse)
async def get_recommendations(
    user_id: str,
    force_refresh: bool = False,
    service: RecommendationService = Depends(get_recommendation_service),
    current_user=Depends(get_current_user),
):
    # Fetch learning profile from user (assumes learning_profile stored on user model)
    learning_profile = getattr(current_user, "learning_profile", {}) or {}

    rec = await service.get_or_generate(
        user_id=user_id,
        learning_profile=learning_profile,
        force_refresh=force_refresh,
    )
    return RecommendationResponse(
        id=str(rec.id),
        user_id=rec.user_id,
        suggested_topics=rec.suggested_topics,
        weak_areas=rec.weak_areas,
        learning_path=rec.learning_path,
        reasoning=rec.reasoning,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recommendations(
    user_id: str,
    service: RecommendationService = Depends(get_recommendation_service),
    current_user=Depends(get_current_user),
):
    deleted = await service.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recommendation not found")