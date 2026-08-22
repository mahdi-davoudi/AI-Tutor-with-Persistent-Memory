from typing import Optional
from app.services.llm_service import LLMService


class RecommendationEngine:
    
    RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "suggested_topics": {"type": "array", "items": {"type": "string"}},
            "weak_areas": {"type": "array", "items": {"type": "string"}},
            "learning_path": {"type": "array", "items": {"type": "string"}},
            "reasoning": {"type": "string"},
        },
        "required": ["suggested_topics", "weak_areas", "learning_path", "reasoning"],
        "additionalProperties": False,
    }

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def generate(
        self,
        learning_profile: dict,
        memories: list[dict],
    ) -> dict:
        profile_text = self._format_profile(learning_profile)
        memory_text = self._format_memories(memories)

        prompt = f"""Based on the following learner profile and their memory notes, generate a personalized recommendation.

## Learning Profile
{profile_text}

## Recent Memory Notes
{memory_text}
"""

        messages = [
            {
                "role": "system",
                "content": "You are a personalized learning advisor for an AI tutor system.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            parsed, _ = await self.llm_service.generate_structured(
                messages=messages,
                schema=self.RESPONSE_SCHEMA,
                schema_name="learning_recommendation",
            )
        except Exception as e:
            print(f"RECOMMENDATION ENGINE ERROR: {e}")
            parsed = {}

        return {
            "suggested_topics": parsed.get("suggested_topics", []),
            "weak_areas": parsed.get("weak_areas", []),
            "learning_path": parsed.get("learning_path", []),
            "reasoning": parsed.get("reasoning"),
        }

    def _format_profile(self, profile: dict) -> str:
        if not profile:
            return "No learning profile available yet."
        lines = []
        for key, value in profile.items():
            if key not in ("user_id", "id", "created_at", "updated_at"):
                lines.append(f"- {key}: {value}")
        return "\n".join(lines) if lines else "Empty profile."

    def _format_memories(self, memories: list[dict]) -> str:
        if not memories:
            return "No memories recorded yet."
        lines = []
        for m in memories[:10]: 
            content = m.get("content") or m.get("text") or str(m)
            lines.append(f"- {content}")
        return "\n".join(lines)
