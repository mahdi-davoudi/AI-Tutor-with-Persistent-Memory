from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field
from pymongo import IndexModel, ASCENDING


class Role(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ChatSession(Document):
    user_id: str
    title: str = "New Chat"
    message_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "chat_sessions"
        indexes = [
            IndexModel([("user_id", ASCENDING)]),
        ]


class Message(Document):
    session_id: str
    role: Role
    content: str
    tokens_used: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "messages"
        indexes = [
            IndexModel([("session_id", ASCENDING), ("created_at", ASCENDING)]),
        ]