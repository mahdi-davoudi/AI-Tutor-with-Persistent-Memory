import math
from dataclasses import dataclass
from app.domain.skill_tracker import SkillEntry, SkillMap


@dataclass
class TopicMastery:
    topic: str
    mastery: float
    level: str
    strong: list[str]
    weak: list[str]
    total_skills: int


_LEVELS = [(0.65, "advanced"), (0.35, "intermediate"), (0.0, "beginner")]

_NEUTRAL_FALLBACK_MASTERY = {
    "advanced": 0.75,
    "intermediate": 0.45,
    "beginner": 0.15,
}


class MasteryEstimator:

    @staticmethod
    def estimate(skill_map: SkillMap) -> dict[str, TopicMastery]:
        return {
            topic: MasteryEstimator._score(topic, skills)
            for topic, skills in skill_map.items()
        }

    @staticmethod
    def _score(topic: str, skills: dict[str, SkillEntry]) -> TopicMastery:
        strong_list, weak_list = [], []
        raw_score = max_score = 0.0

        for subtopic, entry in skills.items():
            w = entry.importance * math.log1p(entry.frequency)
            if entry.tag == "strong":
                raw_score += w
                max_score += w
                strong_list.append(subtopic)
            elif entry.tag == "weak":
                raw_score -= w
                max_score += w
                weak_list.append(subtopic)

        if max_score == 0.0:
            mastery = MasteryEstimator._fallback_from_hints(skills)
        else:
            mastery = round((raw_score + max_score) / (2 * max_score), 4)

        mastery = max(0.0, min(1.0, mastery))
        level = next(label for threshold, label in _LEVELS if mastery >= threshold)

        return TopicMastery(
            topic=topic,
            mastery=mastery,
            level=level,
            strong=strong_list,
            weak=weak_list,
            total_skills=len(skills),
        )

    @staticmethod
    def _fallback_from_hints(skills: dict[str, SkillEntry]) -> float:
        hints = [e.level_hint for e in skills.values() if e.level_hint]
        if "advanced" in hints:
            return _NEUTRAL_FALLBACK_MASTERY["advanced"]
        if "intermediate" in hints:
            return _NEUTRAL_FALLBACK_MASTERY["intermediate"]
        return _NEUTRAL_FALLBACK_MASTERY["beginner"]