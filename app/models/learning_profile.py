from pydantic import Field
from beanie import Document
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone
from pymongo import IndexModel, ASCENDING


class TopicProfile(BaseModel):
    mastery: float = Field(ge=0.0, le=1.0)
    level: str                   # "beginner" | "intermediate" | "advanced"
    strong: list[str] = Field(default_factory=list)
    weak: list[str] = Field(default_factory=list)
    total_skills: int = 0


class LearningProfile(Document):
    user_id: str
    topics: dict[str, TopicProfile] = Field(default_factory=dict)
    preferred_style: Optional[str] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "learning_profiles"
        indexes = [
            IndexModel([("user_id", ASCENDING)], unique=True),
        ]