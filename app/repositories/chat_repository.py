from typing import Optional
from app.models.chat import Message, ChatSession


class ChatRepository:
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        return await ChatSession.get(session_id)

    async def get_latest_session_for_user(self, user_id: str) -> Optional[ChatSession]:
        sessions = (
            await ChatSession.find(ChatSession.user_id == user_id)
            .sort(-ChatSession.updated_at)
            .limit(1)
            .to_list()
        )
        return sessions[0] if sessions else None

    async def get_or_create_latest_session(self, user_id: str) -> ChatSession:
        session = await self.get_latest_session_for_user(user_id)
        if session:
            return session
        session = ChatSession(user_id=user_id)
        return await self.create_session(session)

    async def create_session(self, session: ChatSession) -> ChatSession:
        await session.insert()
        return session

    async def update_session(self, session: ChatSession) -> None:
        await session.replace()

    async def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens_used: int | None = None,
    ) -> Message:
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
        )
        await message.insert()
        return message

    async def get_messages(self, session_id: str, limit: int = 20) -> list[Message]:
        messages = (
            await Message.find(Message.session_id == session_id)
            .sort(-Message.created_at)
            .limit(limit)
            .to_list()
        )
        return list(reversed(messages))