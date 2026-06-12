from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UpsertMemoryRequest(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    memory_type: str = "learning_topic"   
    topic: Optional[str] = None    


class MemoryResponse(BaseModel):
    id: str
    user_id: str
    key: str
    value: str
    importance: float
    memory_type: str = "learning_topic"  
    topic: Optional[str] = None      
    source_session_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}