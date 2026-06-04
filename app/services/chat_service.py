from datetime import datetime, timezone
from typing import Optional

import anthropic
from beanie.operators import Set

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models.chat import ChatSession, Message
from app.schemas.chat import (
    ChatSessionResponse,
    ChatTurnResponse,
    CreateSessionRequest,
    MessageResponse,
    SendMessageRequest,
)


def _session_to_response(session: ChatSession) -> ChatSessionResponse:
    return ChatSessionResponse(
        id=str(session.id),
        user_id=session.user_id,
        title=session.title,
        is_active=session.is_active,
        message_count=session.message_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _message_to_response(msg: Message) -> MessageResponse:
    return MessageResponse(
        id=str(msg.id),
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        tokens_used=msg.tokens_used,
        created_at=msg.created_at,
    )


class ChatService:
    def __init__(self) -> None:
        settings = get_settings()
        self._anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Sessions
    # ------------------------------------------------------------------------

    async def create_session(
        self, user_id: str, payload: CreateSessionRequest
    ) -> ChatSessionResponse:
        session = ChatSession(user_id=user_id, title=payload.title or "New Chat")
        await session.insert()
        return _session_to_response(session)

    async def list_sessions(self, user_id: str) -> list[ChatSessionResponse]:
        sessions = await ChatSession.find(
            ChatSession.user_id == user_id,
            ChatSession.is_active == True,
        ).sort(-ChatSession.updated_at).to_list()
        return [_session_to_response(s) for s in sessions]

    async def get_session(self, session_id: str, user_id: str) -> ChatSessionResponse:
        session = await self._fetch_owned_session(session_id, user_id)
        return _session_to_response(session)

    async def delete_session(self, session_id: str, user_id: str) -> None:
        session = await self._fetch_owned_session(session_id, user_id)
        await session.update(Set({"is_active": False, "updated_at": datetime.now(timezone.utc)}))

    # Messages
    # ------------------------------------------------------------------

    async def list_messages(
        self, session_id: str, user_id: str
    ) -> list[MessageResponse]:
        await self._fetch_owned_session(session_id, user_id)  
        messages = await Message.find(
            Message.session_id == session_id
        ).sort(+Message.created_at).to_list()
        return [_message_to_response(m) for m in messages]

    async def send_message(
        self,
        session_id: str,
        user_id: str,
        payload: SendMessageRequest,
    ) -> ChatTurnResponse:
        session = await self._fetch_owned_session(session_id, user_id)

        # Persist the user turn
        user_msg = Message(
            session_id=session_id,
            role="user",
            content=payload.content,
        )
        await user_msg.insert()

        # Build conversation history for the AI (last 20 messages keeps context manageable)
        history = await Message.find(
            Message.session_id == session_id,
        ).sort(+Message.created_at).limit(20).to_list()

        ai_messages = [
            {"role": m.role, "content": m.content}
            for m in history
            if m.role in ("user", "assistant")
        ]

        # Call Anthropic Claude
        ai_response = await self._anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system="You are a helpful assistant.",
            messages=ai_messages,
        )

        assistant_content = ai_response.content[0].text
        tokens_used = ai_response.usage.output_tokens

        # Persist the assistant turn
        assistant_msg = Message(
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            tokens_used=tokens_used,
        )
        await assistant_msg.insert()

        # Update session metadata
        now = datetime.now(timezone.utc)
        new_count = session.message_count + 2
        new_title = session.title
        if session.message_count == 0:
            # Auto-title from first user message
            new_title = payload.content[:60] + ("…" if len(payload.content) > 60 else "")

        await session.update(
            Set({
                "message_count": new_count,
                "title": new_title,
                "updated_at": now,
            })
        )
        await session.sync()

        return ChatTurnResponse(
            user_message=_message_to_response(user_msg),
            assistant_message=_message_to_response(assistant_msg),
            session=_session_to_response(session),
        )

    # Helpers
    # ------------------------------------------------------------------

    async def _fetch_owned_session(self, session_id: str, user_id: str) -> ChatSession:
        session = await ChatSession.get(session_id)
        if not session:
            raise NotFoundError("ChatSession", session_id)
        if session.user_id != user_id:
            raise AuthorizationError("Access denied.")
        return session