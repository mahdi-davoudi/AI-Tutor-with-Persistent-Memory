import json

from app.services.llm_service import LLMService


class MemoryExtractor:

    SYSTEM_PROMPT = """
You are a memory extraction engine.

Extract only useful long-term learning memories.

Return ONLY valid JSON.

Format:

[
    {
        "key": "learning_topic_fastapi",
        "value": "beginner",
        "importance": 0.8
    }
]

Rules:

- Extract only facts worth remembering.
- Ignore greetings.
- Ignore temporary questions.
- Maximum 5 memories.
- Return [] if nothing important exists.
"""

    def __init__(self, llm: LLMService):
        self.llm = llm

    async def extract(
        self,
        user_message: str,
        assistant_response: str,
    ) -> list[dict]:

        messages = [
            {
                "role": "user",
                "content": f"""
User Message:
{user_message}

Assistant Response:
{assistant_response}
""",
            }
        ]
        try:
            original_prompt = self.llm.SYSTEM_PROMPT
            
            response, _ = await self.llm.generate(
                messages,
                system_prompt=self.SYSTEM_PROMPT,
            )
            self.llm.SYSTEM_PROMPT = original_prompt

            memories = json.loads(response)
            if not isinstance(memories, list):
                return []

            return memories

        except Exception:
            return []