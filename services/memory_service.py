"""
app/services/memory_service.py
───────────────────────────────
Business logic for the memory feature.

Current state  : Basic CRUD operations on MemoryDocument.
Future roadmap :

  Phase 2 – Automatic extraction
  --------------------------------
  After each chat turn, a background task will analyse the conversation and
  extract memorable facts (e.g. "User works in NLP", "User prefers Python").
  An LLM or a specialised extraction model can power this step.

  Phase 3 – Importance scoring
  --------------------------------
  Extracted memories are scored (0-1) by a scoring model.  High-importance
  memories are retained; low-importance ones decay over time via a scheduled
  cleanup job.

  Phase 4 – Semantic retrieval
  --------------------------------
  Each memory will carry a dense vector embedding (e.g. from
  `sentence-transformers`).  At chat time, MemoryService.retrieve_relevant()
  will perform an approximate nearest-neighbour search to return the K most
  contextually relevant memories.  These are then injected into the prompt
  by ChatService.

  Phase 5 – Vector database integration
  --------------------------------
  Embeddings and ANN search are offloaded to a dedicated vector store
  (Qdrant, Weaviate, Pinecone, …).  MemoryDocument in MongoDB retains the
  text + metadata; the vector store handles similarity queries.

All of the above integrates here without changing any route handlers.
"""

import logging
from typing import Optional

from beanie import PydanticObjectId

from app.models.memory import MemoryDocument
from app.schemas.memory import CreateMemoryRequest

logger = logging.getLogger(__name__)


class MemoryService:
    """
    CRUD layer for user memories.

    Methods are named to match the future-state interface so callers
    won't need to change when Phase 2+ features are activated.
    """

    # ── Create ─────────────────────────────────────────────────────────────────

    async def create_memory(
        self,
        request: CreateMemoryRequest,
    ) -> MemoryDocument:
        """
        Persist a new memory entry manually.

        In future phases this will also:
        - Generate and store an embedding.
        - Upsert the vector into the vector store.
        """
        doc = MemoryDocument(
            user_id=request.user_id,
            memory=request.memory,
            importance=request.importance,
        )
        await doc.insert()
        logger.debug(
            "Created memory for user_id=%s: '%s'",
            request.user_id,
            request.memory[:60],
        )
        return doc

    # ── Read ───────────────────────────────────────────────────────────────────

    async def get_memories(
        self,
        user_id: str,
        min_importance: float = 0.0,
        limit: Optional[int] = None,
    ) -> list[MemoryDocument]:
        """
        Return memories for a user, ordered by importance (highest first).

        Parameters
        ----------
        user_id : str
        min_importance : float
            Filter out memories below this threshold.
        limit : int | None
            Cap the result set.
        """
        query = MemoryDocument.find(
            MemoryDocument.user_id == user_id,
            MemoryDocument.importance >= min_importance,
            sort=-MemoryDocument.importance,
        )
        if limit is not None:
            query = query.limit(limit)

        memories: list[MemoryDocument] = await query.to_list()
        return memories

    # ── Update ─────────────────────────────────────────────────────────────────

    async def update_importance(
        self,
        memory_id: str,
        importance: float,
    ) -> Optional[MemoryDocument]:
        """
        Adjust the importance score of an existing memory.

        Returns the updated document, or None if not found.
        """
        try:
            oid = PydanticObjectId(memory_id)
        except Exception:
            raise ValueError(f"Invalid memory_id: '{memory_id}'")

        doc = await MemoryDocument.get(oid)
        if doc is None:
            return None

        doc.importance = max(0.0, min(1.0, importance))
        await doc.save()
        return doc

    # ── Delete ─────────────────────────────────────────────────────────────────

    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory by its id.

        Returns True if deleted, False if not found.
        """
        try:
            oid = PydanticObjectId(memory_id)
        except Exception:
            raise ValueError(f"Invalid memory_id: '{memory_id}'")

        doc = await MemoryDocument.get(oid)
        if doc is None:
            return False

        await doc.delete()
        return True

    # ── Future: semantic retrieval (stub) ──────────────────────────────────────

    async def retrieve_relevant(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[MemoryDocument]:
        """
        [FUTURE] Return the K memories most semantically relevant to `query`.

        Current behaviour: returns top_k memories sorted by importance
        (importance-as-proxy until embeddings are available).

        When Phase 4 is implemented:
        1. Embed `query` using the embedding service.
        2. Run ANN search in the vector store filtered by user_id.
        3. Fetch the corresponding MemoryDocuments from MongoDB.
        4. Return them.
        """
        logger.debug(
            "[retrieve_relevant] Stub: returning top-%d by importance for user=%s",
            top_k,
            user_id,
        )
        return await self.get_memories(user_id=user_id, limit=top_k)