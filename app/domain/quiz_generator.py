class QuizGenerator:

    RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 3,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 4,
                        },
                        "correct_index": {"type": "integer"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["question", "options", "correct_index", "explanation"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["questions"],
        "additionalProperties": False,
    }

    def __init__(self, llm):
        self.llm = llm

    async def generate(self, topic: str, weak_skills: list[str]) -> list[dict]:
        skills_text = ", ".join(weak_skills) if weak_skills else "general fundamentals"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a quiz generator for an AI tutor system. "
                    "Generate 3 to 5 multiple-choice questions (exactly 4 options each) "
                    "that test the user's understanding of their weak skills. "
                    "Each question must have exactly one correct option."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Topic: {topic}\n"
                    f"Weak skills to focus on: {skills_text}\n\n"
                    "Generate the quiz now."
                ),
            },
        ]

        parsed, _ = await self.llm.generate_structured(
            messages=messages,
            schema=self.RESPONSE_SCHEMA,
            schema_name="quiz_generation",
            max_tokens=1500,
        )

        questions = parsed.get("questions", [])
        validated = []
        for q in questions:
            options = q.get("options", [])
            correct_index = q.get("correct_index", -1)

            if len(options) != 4:
                continue
            if not isinstance(correct_index, int) or not (0 <= correct_index < 4):
                continue
            if not q.get("question") or not q.get("explanation"):
                continue

            validated.append({
                "question": q["question"],
                "options": options,
                "correct_index": correct_index,
                "explanation": q["explanation"],
            })

        return validated