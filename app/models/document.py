from datetime import datetime, timezone
from typing import Optional
from beanie import Document
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING


class UserDocument(Document):
    user_id: str
    filename: str
    content_type: str
    status: str = "processing"  # processing | ready | failed
    chunk_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "documents"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
        ]