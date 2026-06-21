from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.chat_repository import ChatRepository
from app.services.memory_service import MemoryService
from app.domain.recommendation_engine import RecommendationEngine
from app.services.llm_service import LLMService
from app.core.exceptions import NotFoundError


class RecommendationService:

    def __init__(self):
        self.repo = RecommendationRepository()
        self.memory_service = MemoryService()
        self.engine = RecommendationEngine(llm_service=LLMService())

    async def get_or_generate(
        self,
        user_id: str,
        learning_profile: dict,
        force_refresh: bool = False,
    ):
        if not force_refresh:
            existing = await self.repo.get_by_user_id(user_id)
            if existing:
                return existing

        memories_raw = await self.memory_service.list_memories(user_id)
        memories = [m.model_dump() for m in memories_raw]

        result = await self.engine.generate(
            learning_profile=learning_profile,
            memories=memories,
        )

        return await self.repo.upsert(user_id, result)

    async def get_existing(self, user_id: str):
        rec = await self.repo.get_by_user_id(user_id)
        if not rec:
            raise NotFoundError(f"No recommendation found for user {user_id}")
        return rec

    async def delete(self, user_id: str) -> bool:
        return await self.repo.delete_by_user_id(user_id)