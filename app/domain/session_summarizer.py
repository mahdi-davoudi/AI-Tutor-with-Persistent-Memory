from app.services.llm_service import LLMService

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
    },
    "required": ["summary"],
    "additionalProperties": False,
}


class SessionSummarizer:
    """
    Maintains a rolling narrative summary of a tutoring conversation so the
    tutor retains long-term context beyond the raw message window that gets
    loaded into the prompt on every turn.
    """

    SUMMARIZE_EVERY_N_MESSAGES = 10  

    def __init__(self, llm: LLMService):
        self.llm = llm

    def should_summarize(self, message_count: int, last_summarized_count: int) -> bool:
        return (message_count - last_summarized_count) >= self.SUMMARIZE_EVERY_N_MESSAGES

    async def summarize(
        self,
        previous_summary: str | None,
        recent_messages: list[dict],
    ) -> tuple[str, int]:
        history_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in recent_messages
        )

        instruction = (
            "You maintain a running summary of a tutoring conversation between "
            "an AI tutor and a student, so the tutor can remember long-term "
            "context beyond what fits in the visible chat window.\n\n"
            f"Previous summary:\n{previous_summary or '(none yet)'}\n\n"
            f"New messages since then:\n{history_text}\n\n"
            "Write an updated summary (max ~150 words). Capture: topics "
            "covered, key concepts already explained, unresolved questions, "
            "the student's current focus, and their overall learning "
            "trajectory. Merge with the previous summary rather than just "
            "appending — drop stale details that are no longer relevant."
        )

        messages = [{"role": "system", "content": instruction}]

        result, tokens = await self.llm.generate_structured(
            messages=messages,
            schema=SUMMARY_SCHEMA,
            schema_name="session_summary",
            max_tokens=400,
        )
        return result["summary"], tokens