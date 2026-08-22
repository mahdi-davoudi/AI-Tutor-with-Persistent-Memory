from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Optional
from beanie import Document


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str


class Quiz(Document):
    user_id: str
    topic: str
    weak_skills: list[str] = Field(default_factory=list)
    questions: list[QuizQuestion]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "quizzes"
        indexes = ["user_id"]