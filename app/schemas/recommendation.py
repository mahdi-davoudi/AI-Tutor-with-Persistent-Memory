from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    id: str
    user_id: str
    suggested_topics: list[str]
    weak_areas: list[str]
    learning_path: list[str]
    reasoning: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecommendationRequest(BaseModel):
    force_refresh: bool = False