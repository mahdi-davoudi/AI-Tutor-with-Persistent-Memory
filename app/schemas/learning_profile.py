from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TopicProfileSchema(BaseModel):
    mastery: float = Field(ge=0.0, le=1.0)
    level: str
    strong: list[str] = Field(default_factory=list)
    weak: list[str] = Field(default_factory=list)
    total_skills: int = 0

    model_config = {"from_attributes": True}


class LearningProfileResponse(BaseModel):
    user_id: str
    topics: dict[str, TopicProfileSchema] = Field(default_factory=dict)
    preferred_style: Optional[str] = None
    generated_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LearningProfileSummary(BaseModel):
    user_id: str
    topics: dict[str, TopicProfileSchema]
    preferred_style: Optional[str]