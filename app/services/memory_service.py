import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from beanie.operators import Set, Inc, In
from qdrant_client.models import (
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointIdsList,
    PointStruct,
)
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.vector_db import get_qdrant_client
from app.models.memory import Memory
from app.schemas.memory import MemoryResponse, UpsertMemoryRequest
from app.services.embedding_service import get_embedding_service
from beanie import PydanticObjectId
logger = logging.getLogger(__name__)


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


def _point_id(memory_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, memory_id))


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
            await self._sync_vector(existing)
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
        await self._sync_vector(memory)

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
    async def search_similar(
        self,
        user_id: str,
        query_text: str,
        limit: int = 5,
    ) -> list[Memory]:
        try:
            settings = get_settings()
            embedding_service = get_embedding_service()
            client = get_qdrant_client()

            query_vector = await embedding_service.embed(query_text)

            result = await client.query_points(
                collection_name=settings.qdrant_collection_name,
                query=query_vector,
                query_filter=Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                ),
                limit=limit,
            )

            memory_ids = [point.payload["memory_id"] for point in result.points]
            if not memory_ids:
                return []

            memories = await Memory.find(
                In(Memory.id, [PydanticObjectId(mid) for mid in memory_ids])
            ).to_list()

            order = {mid: i for i, mid in enumerate(memory_ids)}
            memories.sort(key=lambda m: order.get(str(m.id), len(memory_ids)))
            return memories
        except Exception as exc:
            logger.warning(f"Semantic memory search failed for user {user_id}: {exc}")
            return []

    async def get(self, user_id: str, memory_id: str) -> MemoryResponse:
        memory = await self._fetch_owned(user_id, memory_id)
        return _to_response(memory)

    async def delete(self, user_id: str, memory_id: str) -> None:
        memory = await self._fetch_owned(user_id, memory_id)
        await memory.delete()
        await self._delete_vector(memory_id)

    async def delete_all(self, user_id: str) -> int:
        result = await Memory.find(Memory.user_id == user_id).delete()
        await self._delete_vectors_for_user(user_id)
        return result.deleted_count if result else 0

    
    async def _fetch_owned(self, user_id: str, memory_id: str) -> Memory:
        memory = await Memory.get(memory_id)
        if not memory:
            raise NotFoundError("Memory", memory_id)
        if memory.user_id != user_id:
            raise NotFoundError("Memory", memory_id)
        return memory

    # Vector sync (best-effort — Mongo write must never fail because of Qdrant)
    async def _sync_vector(self, memory: Memory) -> None:
        try:
            settings = get_settings()
            embedding_service = get_embedding_service()
            client = get_qdrant_client()

            text = f"{memory.key}: {memory.value}"
            vector = await embedding_service.embed(text)

            await client.upsert(
                collection_name=settings.qdrant_collection_name,
                points=[
                    PointStruct(
                        id=_point_id(str(memory.id)),
                        vector=vector,
                        payload={
                            "memory_id": str(memory.id),
                            "user_id": memory.user_id,
                            "key": memory.key,
                            "value": memory.value,
                            "memory_type": memory.memory_type,
                            "topic": memory.topic,
                        },
                    )
                ],
            )
        except Exception as exc:
            logger.warning(f"Failed to sync memory {memory.id} to Qdrant: {exc}")

    async def _delete_vector(self, memory_id: str) -> None:
        try:
            settings = get_settings()
            client = get_qdrant_client()
            await client.delete(
                collection_name=settings.qdrant_collection_name,
                points_selector=PointIdsList(points=[_point_id(memory_id)]),
            )
        except Exception as exc:
            logger.warning(f"Failed to delete vector for memory {memory_id}: {exc}")

    async def _delete_vectors_for_user(self, user_id: str) -> None:
        try:
            settings = get_settings()
            client = get_qdrant_client()
            await client.delete(
                collection_name=settings.qdrant_collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                    )
                ),
            )
        except Exception as exc:
            logger.warning(f"Failed to delete vectors for user {user_id}: {exc}")