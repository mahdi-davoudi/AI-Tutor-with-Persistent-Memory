import json
from app.services.llm_service import LLMService


class MemoryExtractor:

    SYSTEM_PROMPT = """
You are a memory extraction engine for an AI tutor system.
Extract learning-related facts from the conversation below.

Output ONLY a JSON array. No explanation. No markdown. No code blocks. Just the raw JSON array.

Each item must have exactly these fields:
- "key": unique snake_case identifier, e.g. "python_loops_skill"
- "value": concise description of what was learned or observed
- "importance": float 0.0–1.0 (how important is this for future tutoring)
- "confidence": float 0.0–1.0 (how confident are you in this extraction)
- "memory_type": one of ["learning_topic", "skill_level", "user_preference", "weak_area", "strong_area"]
- "topic": the subject area, e.g. "python", "math", "machine_learning"

Rules:
- Maximum 5 items per conversation.
- Only extract facts that are genuinely useful for personalizing future tutoring.
- For importance: 0.9+ = critical gaps or strong skills, 0.6–0.8 = useful context, below 0.5 = skip it.
- If nothing meaningful to extract, output exactly: []

Example output:
[
  {
    "key": "python_recursion_skill",
    "value": "struggles with base cases in recursive functions",
    "importance": 0.85,
    "confidence": 0.9,
    "memory_type": "weak_area",
    "topic": "python"
  }
]
"""


    def __init__(self, llm: LLMService):
        self.llm = llm

    async def extract(
        self,
        user_message: str,
        assistant_response: str,
    ) -> list[dict]:
        trimmed_response = assistant_response[:800]
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Extract memories from this conversation:\n\n"
                    f"User: {user_message}\n\n"
                    f"Assistant: {trimmed_response}"
                ),
            },
        ]

        try:
            response, _ = await self.llm.generate(messages)

            # clean markdown if model wraps in ```json
            cleaned = response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            memories = json.loads(cleaned)

            if not isinstance(memories, list):
                return []
            validated = []
            for m in memories:
                if not m.get("key") or not m.get("value"):
                    continue

                m.setdefault("importance", 0.5)
                m.setdefault("confidence", 0.8)
                m.setdefault("memory_type", "learning_topic")
                m.setdefault("topic", "general")

                m["importance"] = max(0.0, min(1.0, float(m["importance"])))
                m["confidence"] = max(0.0, min(1.0, float(m["confidence"])))

                valid_types = {
                    "learning_topic", "skill_level",
                    "user_preference", "weak_area", "strong_area"
                }
                if m["memory_type"] not in valid_types:
                    m["memory_type"] = "learning_topic"

                validated.append(m)

            return validated

        except json.JSONDecodeError as e:
            print(f"MEMORY EXTRACTOR JSON ERROR: {e} | raw: {response[:200]}")
            return []
        except Exception as e:
            print(f"MEMORY EXTRACTOR ERROR: {e}")
            return []