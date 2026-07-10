from datetime import datetime, timezone
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING


class Memory(Document):
    user_id: str
    memory_type : str
    topic: str
    key: str
    value: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence : float = 0.8
    frequency: int = 1
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "memories"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("key", ASCENDING)], unique=True),
            IndexModel([("user_id", ASCENDING), ("importance", DESCENDING)]),
        ]