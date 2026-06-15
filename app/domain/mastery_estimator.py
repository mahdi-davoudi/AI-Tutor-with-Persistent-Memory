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
            

        mastery = round((raw_score + max_score) / (2 * max_score), 4) if max_score else 0.0
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