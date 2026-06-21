from typing import Optional
from app.models.recommendation import Recommendation


class RecommendationRepository:

    async def get_by_user_id(self, user_id: str) -> Optional[Recommendation]:
        return await Recommendation.find_one(Recommendation.user_id == user_id)

    async def upsert(self, user_id: str, data: dict) -> Recommendation:
        from datetime import datetime

        existing = await self.get_by_user_id(user_id)
        if existing:
            data["updated_at"] = datetime.utcnow()
            await existing.set(data)
            return existing

        rec = Recommendation(user_id=user_id, **data)
        await rec.insert()
        return rec

    async def delete_by_user_id(self, user_id: str) -> bool:
        existing = await self.get_by_user_id(user_id)
        if existing:
            await existing.delete()
            return True
        return False