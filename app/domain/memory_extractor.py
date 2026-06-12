import json
from app.services.llm_service import LLMService


class MemoryExtractor:

    SYSTEM_PROMPT = """
You are a memory extraction engine. Your only job is to extract learning-related facts from conversations.

Output ONLY a JSON array. No explanation. No markdown. No code blocks. Just the raw JSON array.

Example output:
[{"key": "learning_topic_neural_network", "value": "beginner", "importance": 0.8}]

Rules:
- Extract facts about what the user is learning and their level.
- Maximum 5 items.
- If nothing to extract, output exactly: []
"""

    def __init__(self, llm: LLMService):
        self.llm = llm

    async def extract(
        self,
        user_message: str,
        assistant_response: str,
    ) -> list[dict]:

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract memories from this conversation:\n\nUser said: {user_message}\n\nAssistant said: {assistant_response[:300]}",
            },
        ]
        try:
            response, _ = await self.llm.generate(messages)

            # clean markdown if model wraps in ```json
            cleaned = response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            memories = json.loads(cleaned)

            if not isinstance(memories, list):
                return []
            for m in memories:
                if "topic" not in m:
                    parts = m.get("key", "").split("_")
                    m["topic"] = parts[-1] if parts else "general"
                if "memory_type" not in m:
                    m["memory_type"] = "learning_topic"

            return memories
        except Exception as e:
            print(f"MEMORY EXTRACTOR ERROR: {e}")
            return []