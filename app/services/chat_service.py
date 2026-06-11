from datetime import datetime, timezone

from app.models.chat import Message, ChatSession
from app.repositories.chat_repository import ChatRepository
from app.domain.prompt_builder import PromptBuilder
from app.domain.session_policy import SessionPolicy
from app.services.llm_service import LLMService


class ChatService:

    def __init__(self, repo: ChatRepository, llm: LLMService, memory_service, memory_extractor):
        self.repo = repo
        self.llm = llm
        self.memory_service = memory_service
        self.memory_extractor = memory_extractor

    async def _get_or_create_session(self, user_id: str) -> ChatSession:
        sessions = (
            await ChatSession.find(ChatSession.user_id == user_id)
            .sort(-ChatSession.updated_at)
            .limit(1)
            .to_list()
        )

        if sessions:
            return sessions[0]

        session = ChatSession(user_id=user_id)
        await self.repo.create_session(session)
        return session

    async def _extract_and_store_memories(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        answer: str,
    ):
        memories = await self.memory_extractor.extract(
            user_message=user_message,
            assistant_response=answer,
        )

        from app.schemas.memory import UpsertMemoryRequest

        for memory in memories:
            try:
                payload = UpsertMemoryRequest(
                    key=memory["key"],
                    value=memory["value"],
                    importance=memory.get("importance", 0.5),
                )
                await self.memory_service.upsert(
                    user_id=user_id,
                    payload=payload,
                    source_session_id=session_id,
                )
            except Exception:
                continue

    # ─── Main Method 
    async def send_message(self, user_id: str, content: str):

        session = await self._get_or_create_session(user_id)
        session_id = str(session.id)

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

        # 4. Build prompt
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

        # 7. Extract and store memories
        await self._extract_and_store_memories(
            user_id=user_id,
            session_id=session_id,
            user_message=content,
            answer=answer,
        )

        # 8. Update session metadata
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

        # 9. Return response
        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "session_id": session_id,
        }