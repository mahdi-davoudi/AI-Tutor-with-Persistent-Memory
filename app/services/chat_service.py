from datetime import datetime, timezone

from app.models.chat import Message, ChatSession
from app.repositories.chat_repository import ChatRepository
from app.domain.prompt_builder import PromptBuilder
from app.domain.session_policy import SessionPolicy
from app.services.llm_service import LLMService


class ChatService:

    def __init__(self, repo: ChatRepository, llm: LLMService):
        self.repo = repo
        self.llm = llm

    async def send_message(self, session_id: str, user_id: str, content: str):

        # 1. Load session
        session = await self.repo.get_session(session_id)

        if not session or session.user_id != user_id:
            raise PermissionError("Access denied")

        # 2. Save user message
        user_msg = Message(
            session_id=session_id,
            role="user",
            content=content,
        )
        await self.repo.create_message(user_msg)

        # 3. Get history
        history = await self.repo.get_messages(session_id, limit=20)

        history_dict = [
            {"role": m.role, "content": m.content}
            for m in history
        ]

        # 4. Build prompt (domain logic)
        messages = PromptBuilder.build(history_dict, content)

        # 5. Call LLM
        answer, tokens = await self.llm.generate(messages)

        # 6. Save assistant message
        assistant_msg = Message(
            session_id=session_id,
            role="assistant",
            content=answer,
            tokens_used=tokens,
        )
        await self.repo.create_message(assistant_msg)

        # 7. Update session metadata (domain rule)
        new_count = len(history) + 2

        update_data = {
            "message_count": new_count,
            "updated_at": datetime.now(timezone.utc),
        }

        if SessionPolicy.should_auto_title(session.message_count):
            update_data["title"] = SessionPolicy.generate_title(content)

        session.message_count = new_count
        session.updated_at = update_data["updated_at"]

        if "title" in update_data:
            session.title = update_data["title"]

        await self.repo.update_session(session)

        # 8. Return response
        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "session": session,
        }