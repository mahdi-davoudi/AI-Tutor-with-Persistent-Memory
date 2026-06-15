from datetime import datetime, timezone
from typing import Any, Optional
from app.domain.skill_tracker import SkillTracker
from app.domain.mastery_estimator import MasteryEstimator
from app.models.learning_profile import LearningProfile, TopicProfile
from app.models.memory import Memory
from app.schemas.learning_profile import (
    LearningProfileResponse,
    LearningProfileSummary,
    TopicProfileSchema,
)
from app.core.exceptions import NotFoundError

_STYLE_SIGNALS = {
    "example-based": ["example", "show me", "demonstrate", "sample"],
    "theory-first":  ["explain", "why", "concept", "theory"],
    "practice-oriented": ["exercise", "practice", "quiz", "drill"],
}


class ProfileService:

    async def generate_profile(self, user_id: str) -> LearningProfileResponse:
        memories = await Memory.find(Memory.user_id == user_id).to_list()
        raw = [m.model_dump() for m in memories]

        skill_map = SkillTracker.build(raw)
        mastery_map = MasteryEstimator.estimate(skill_map)
        preferred_style = self._detect_style(raw)

        topics: dict[str, TopicProfile] = {
            topic: TopicProfile(
                mastery=tm.mastery,
                level=tm.level,
                strong=tm.strong,
                weak=tm.weak,
                total_skills=tm.total_skills,
            )
            for topic, tm in mastery_map.items()
        }

        now = datetime.now(timezone.utc)
        existing = await LearningProfile.find_one(LearningProfile.user_id == user_id)

        if existing:
            existing.topics = topics
            existing.preferred_style = preferred_style
            existing.updated_at = now
            await existing.save()
            profile = existing
        else:
            profile = LearningProfile(
                user_id=user_id,
                topics=topics,
                preferred_style=preferred_style,
                generated_at=now,
                updated_at=now,
            )
            await profile.insert()

        return self._to_response(profile)

    async def get_profile(self, user_id: str) -> LearningProfileResponse:
        profile = await LearningProfile.find_one(LearningProfile.user_id == user_id)
        if not profile:
            raise NotFoundError("LearningProfile", user_id)
        return self._to_response(profile)

    async def get_summary(self, user_id: str) -> LearningProfileSummary:
        profile = await LearningProfile.find_one(LearningProfile.user_id == user_id)
        if not profile:
            return LearningProfileSummary(user_id=user_id, topics={}, preferred_style=None)
        r = self._to_response(profile)
        return LearningProfileSummary(user_id=user_id, topics=r.topics, preferred_style=r.preferred_style)

    async def delete_profile(self, user_id: str) -> None:
        profile = await LearningProfile.find_one(LearningProfile.user_id == user_id)
        if not profile:
            raise NotFoundError("LearningProfile", user_id)
        await profile.delete()

    @staticmethod
    def _detect_style(raw: list[dict]) -> Optional[str]:
        counts = {s: 0 for s in _STYLE_SIGNALS}
        for mem in raw:
            content = (mem.get("value") or "").lower()
            for style, kws in _STYLE_SIGNALS.items():
                if any(kw in content for kw in kws):
                    counts[style] += 1
        total = sum(counts.values())
        if not total:
            return None
        best = max(counts, key=lambda s: counts[s])
        return best if counts[best] / total > 0.4 else None

    @staticmethod
    def _to_response(profile: LearningProfile) -> LearningProfileResponse:
        return LearningProfileResponse(
            user_id=profile.user_id,
            topics={
                name: TopicProfileSchema(
                    mastery=tp.mastery,
                    level=tp.level,
                    strong=tp.strong,
                    weak=tp.weak,
                    total_skills=tp.total_skills,
                )
                for name, tp in profile.topics.items()
            },
            preferred_style=profile.preferred_style,
            generated_at=profile.generated_at,
            updated_at=profile.updated_at,
        )