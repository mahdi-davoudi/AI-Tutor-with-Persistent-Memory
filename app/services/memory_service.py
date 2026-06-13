from datetime import datetime, timezone
from typing import Optional

from beanie.operators import Set, Inc

from app.core.exceptions import NotFoundError
from app.models.memory import Memory
from app.schemas.memory import MemoryResponse, UpsertMemoryRequest


def _to_response(memory: Memory) -> MemoryResponse:
    return MemoryResponse(
        id=str(memory.id),
        user_id=memory.user_id,
        key=memory.key,
        value=memory.value,
        importance=memory.importance,
        memory_type=memory.memory_type,       
        topic=memory.topic, 
        frequency=memory.frequency,       
        confidence=memory.confidence,  
        source_session_id=memory.source_session_id,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


class MemoryService:
    async def upsert(
        self,
        user_id: str,
        payload: UpsertMemoryRequest,
        source_session_id: Optional[str] = None,
    ) -> MemoryResponse:
        
        existing = await Memory.find_one(
            Memory.user_id == user_id,
            Memory.key == payload.key,
        )
        if existing:
            await existing.update(
                Set({
                    "value": payload.value,
                    "importance": payload.importance,
                    "memory_type": payload.memory_type,    
                    "topic": payload.topic or "general",
                    "last_accessed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }),
                Inc({"frequency": 1}),
            )
            await existing.sync()
            return _to_response(existing)

        memory = Memory(
            user_id=user_id,
            key=payload.key,
            value=payload.value,
            importance=payload.importance,
            memory_type=payload.memory_type,      
            topic=payload.topic or "general", 
            source_session_id=source_session_id,
        )
        await memory.insert()

        return _to_response(memory)

    async def list_memories(
        self,
        user_id: str,
        min_importance: float = 0.0,
    ) -> list[MemoryResponse]:
        memories = await Memory.find(
            Memory.user_id == user_id,
            Memory.importance >= min_importance,
        ).sort(-Memory.importance).to_list()
        return [_to_response(m) for m in memories]

    async def get(self, user_id: str, memory_id: str) -> MemoryResponse:
        memory = await self._fetch_owned(user_id, memory_id)
        return _to_response(memory)

    async def delete(self, user_id: str, memory_id: str) -> None:
        memory = await self._fetch_owned(user_id, memory_id)
        await memory.delete()

    async def delete_all(self, user_id: str) -> int:
        result = await Memory.find(Memory.user_id == user_id).delete()
        return result.deleted_count if result else 0

    # Helper
    # ------------------------------------------------------------------

    async def _fetch_owned(self, user_id: str, memory_id: str) -> Memory:
        memory = await Memory.get(memory_id)
        if not memory:
            raise NotFoundError("Memory", memory_id)
        if memory.user_id != user_id:
            raise NotFoundError("Memory", memory_id)  
        return memory