from datetime import datetime
from pydantic import BaseModel


class QuizQuestionResponse(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str


class QuizResponse(BaseModel):
    id: str
    user_id: str
    topic: str
    weak_skills: list[str]
    questions: list[QuizQuestionResponse]
    created_at: datetime


class GenerateQuizRequest(BaseModel):
    topic: str | None = None 