from fastapi import APIRouter, Depends, HTTPException, status
from app.services.quiz_service import QuizService
from app.schemas.quiz import QuizResponse, GenerateQuizRequest
from app.core.security import get_current_user
from app.core.exceptions import NotFoundError
from app.models.user import User

router = APIRouter(prefix="/quiz", tags=["quiz"])


def get_quiz_service() -> QuizService:
    return QuizService()


def _to_response(quiz) -> QuizResponse:
    return QuizResponse(
        id=str(quiz.id),
        user_id=quiz.user_id,
        topic=quiz.topic,
        weak_skills=quiz.weak_skills,
        questions=[q.model_dump() for q in quiz.questions],
        created_at=quiz.created_at,
    )

@router.post("/{user_id}/generate", response_model=QuizResponse)
async def generate_quiz(
    user_id: str,
    body: GenerateQuizRequest,
    service: QuizService = Depends(get_quiz_service),
    current_user: User = Depends(get_current_user),
):
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    try:
        quiz = await service.generate_quiz(user_id=user_id, topic=body.topic)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return _to_response(quiz)


@router.get("/{user_id}", response_model=list[QuizResponse])
async def list_quizzes(
    user_id: str,
    service: QuizService = Depends(get_quiz_service),
    current_user: User = Depends(get_current_user),
):
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    quizzes = await service.get_recent(user_id)
    return [_to_response(q) for q in quizzes]