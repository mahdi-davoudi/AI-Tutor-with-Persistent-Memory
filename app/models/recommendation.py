from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field
from bson import ObjectId


class Recommendation(Document):
    user_id: str
    suggested_topics: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    learning_path: list[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "recommendations"