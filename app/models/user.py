from datetime import datetime, timezone
from typing import Optional, Annotated

from beanie import Document, Indexed
from pydantic import Field


class User(Document):
    username: Annotated[str, Indexed(unique=True)]
    email: Annotated[str, Indexed(unique=True)]
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    class Settings:
        name = "users"
        indexes = ["username", "email"]