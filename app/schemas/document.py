from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentChunkResult(BaseModel):
    document_id: str
    filename: str
    chunk_text: str
    score: float