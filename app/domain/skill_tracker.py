import math
from typing import Any
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class SkillEntry:
    subtopic: str
    tag: str          # "weak" | "strong" | "neutral"
    importance: float = 0.5
    frequency: int = 1
    level_hint: str | None = None


SkillMap = dict[str, dict[str, SkillEntry]]

_LEVEL_ALIASES = {
    "beginner": "beginner", "basic": "beginner", "novice": "beginner",
    "intermediate": "intermediate", "medium": "intermediate",
    "advanced": "advanced", "expert": "advanced", "proficient": "advanced",
}


class SkillTracker:

    @staticmethod
    def build(memories: list[dict[str, Any]]) -> SkillMap:
        skill_map: SkillMap = defaultdict(dict)

        for mem in memories:
            topic = (mem.get("topic") or "").strip().lower()
            if not topic or topic == "general":
                continue

            memory_type = (mem.get("memory_type") or "general").strip().lower()
            importance = float(mem.get("importance", 0.5))
            frequency = int(mem.get("frequency", 1))
            value = (mem.get("value") or "").lower()
            key = (mem.get("key") or "").strip().lower()

            # subtopic استخراج: prefix topic رو حذف میکنیم
            # "mblock_beginner_level" → "beginner_level"
            # اما اگه key فقط topic بود → از memory_type استفاده میکنیم
            if key.startswith(f"{topic}_"):
                subtopic = key[len(topic) + 1:]
            else:
                subtopic = key

            # subtopic خیلی عمومی رو reject کن
            generic = {"level", "skill", "general", "topic", "learning"}
            if not subtopic or subtopic in generic:
                subtopic = memory_type  # fallback به memory_type

            if not subtopic:
                continue

            tag = SkillTracker._resolve_tag(memory_type, value)
            level_hint = SkillTracker._parse_level(value) if memory_type == "skill_level" else None

            existing = skill_map[topic].get(subtopic)
            if existing:
                existing.importance = max(existing.importance, importance)
                existing.frequency += frequency
                if tag != "neutral":
                    existing.tag = tag
                if level_hint:
                    existing.level_hint = level_hint
            else:
                skill_map[topic][subtopic] = SkillEntry(
                    subtopic=subtopic,
                    tag=tag,
                    importance=importance,
                    frequency=frequency,
                    level_hint=level_hint,
                )

        return dict(skill_map)

    @staticmethod
    def _resolve_tag(memory_type: str, value: str) -> str:
        if memory_type == "weak_area":
            return "weak"
        if memory_type == "strong_area":
            return "strong"
        if memory_type == "skill_level":
            # از value سطح رو بفهم
            if any(w in value for w in ("beginner", "basic", "novice", "struggling")):
                return "weak"
            if any(w in value for w in ("advanced", "expert", "proficient", "comfortable")):
                return "strong"
            return "neutral"  # intermediate → neutral
        if any(w in value for w in ("struggle", "weak", "difficult", "hard")):
            return "weak"
        if any(w in value for w in ("strong", "comfortable", "master", "good")):
            return "strong"
        return "neutral"

    @staticmethod
    def _parse_level(value: str) -> str | None:
        for alias, canonical in _LEVEL_ALIASES.items():
            if alias in value:
                return canonical
        return None