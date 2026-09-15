import json  
from app.services.llm_service import LLMService
class MemoryExtractor:

    SYSTEM_PROMPT = """
You are a memory extraction engine for an AI tutor system.
Extract learning-related facts from the conversation below.

Rules:
- Maximum 5 items per conversation.
- Only extract facts ABOUT THE USER: their skill level, preferences, weak areas, strong areas, or topics they are actively learning.
- NEVER extract facts, data, citations, page numbers, or details that came from a document or external source quoted in the assistant's answer (e.g. "the file mentions X on page 15"). That is document content, not a fact about the user.
- Only extract facts that are genuinely useful for personalizing future tutoring.
- For importance: 0.9+ = critical gaps or strong skills, 0.6-0.8 = useful context, below 0.5 = skip it.
- If nothing meaningful, return an empty memories array.
"""

    RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "memories": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"},
                        "importance": {"type": "number"},
                        "confidence": {"type": "number"},
                        "memory_type": {
                            "type": "string",
                            "enum": [
                                "learning_topic",
                                "skill_level",
                                "user_preference",
                                "weak_area",
                                "strong_area",
                            ],
                        },
                        "topic": {"type": "string"},
                    },
                    "required": [
                        "key", "value", "importance",
                        "confidence", "memory_type", "topic",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["memories"],
        "additionalProperties": False,
    }
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
            parsed, _ = await self.llm.generate_structured(
                messages=messages,
                schema=self.RESPONSE_SCHEMA,
                schema_name="memory_extraction",
            )

            memories = parsed.get("memories", [])
            if not isinstance(memories, list):
                return []

            validated = []
            for m in memories:
                if not m.get("key") or not m.get("value"):
                    continue

                m["importance"] = max(0.0, min(1.0, float(m.get("importance", 0.5))))
                m["confidence"] = max(0.0, min(1.0, float(m.get("confidence", 0.8))))
                valid_types = {
                    "learning_topic", "skill_level",
                    "user_preference", "weak_area", "strong_area",
                }
                if m.get("memory_type") not in valid_types:
                    m["memory_type"] = "learning_topic"
                    
                m.setdefault("topic", "general")    

                validated.append(m)

            return validated

        except json.JSONDecodeError as e:
            print(f"MEMORY EXTRACTOR JSON ERROR: {e}")
            return []
        except Exception as e:
            print(f"MEMORY EXTRACTOR ERROR: {e}")
            return []