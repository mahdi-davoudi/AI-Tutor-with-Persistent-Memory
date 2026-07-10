from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.chat import Role


# Session

class SessionCreateRequest(BaseModel):
    user_id: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Message 

class ChatMessageCreate(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=8000)


class ChatMessageResponse(BaseModel):
    response: str
    session_id: str
    tokens_used: Optional[int] = None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: Role
    content: str
    tokens_used: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}