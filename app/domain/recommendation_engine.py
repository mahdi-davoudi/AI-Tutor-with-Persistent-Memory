from typing import Optional
from app.services.llm_service import LLMService


class RecommendationEngine:

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def generate(
        self,
        learning_profile: dict,
        memories: list[dict],
    ) -> dict:
        profile_text = self._format_profile(learning_profile)
        memory_text = self._format_memories(memories)

        prompt = f"""You are an expert learning advisor.

Based on the following learner profile and their memory notes, generate a structured recommendation.

## Learning Profile
{profile_text}

## Recent Memory Notes
{memory_text}

Respond ONLY with a valid JSON object, no markdown, no explanation:
{{
  "suggested_topics": ["topic1", "topic2", "topic3"],
  "weak_areas": ["area1", "area2"],
  "learning_path": ["step1", "step2", "step3", "step4", "step5"],
  "reasoning": "brief explanation of why these recommendations were made"
}}
"""

        raw = await self.llm_service.generate(
            messages=[{"role": "user", "content": prompt}],
            system="You are a personalized learning advisor. Always respond with valid JSON only.",
        )

        return self._parse_response(raw)

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

    def _parse_response(self, raw: str) -> dict:
        import json
        import re

        cleaned = re.sub(r"```json|```", "", raw).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = {}

        return {
            "suggested_topics": data.get("suggested_topics", []),
            "weak_areas": data.get("weak_areas", []),
            "learning_path": data.get("learning_path", []),
            "reasoning": data.get("reasoning"),
        }