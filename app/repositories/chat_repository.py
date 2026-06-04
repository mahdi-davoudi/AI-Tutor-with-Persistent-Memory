from typing import List
from app.models.chat import Message, ChatSession


class ChatRepository:
    # Sessions
    # --------------------
    async def get_session(self, session_id: str):
        return await ChatSession.get(session_id)

    async def create_session(self, session: ChatSession):
        await session.insert()
        return session

    async def update_session(self, session: ChatSession):
        await session.save()

    # Messages
    # --------------------
    async def create_message(self, message: Message):
        await message.insert()
        return message

    async def get_messages(self, session_id: str, limit: int = 20):
        return await Message.find(
            Message.session_id == session_id
        ).sort(+Message.created_at).limit(limit).to_list()