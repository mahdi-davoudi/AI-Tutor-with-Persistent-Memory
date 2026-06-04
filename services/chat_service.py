"""
app/services/chat_service.py
─────────────────────────────
Business logic for the chat feature.

Responsibilities
----------------
1. Persist incoming user messages.
2. Load recent conversation history for context.
3. Build a structured prompt (system + history + new message).
4. Delegate generation to LLMService.
5. Persist the assistant response.
6. Return the response to the caller (route handler).

The route handlers contain ZERO business logic; they only call this service.

Prompt format
-------------
We use a plain-text format that most instruction-tuned models understand.
When integrating a chat-template-aware tokenizer (e.g. Qwen2.5's apply_chat_template),
swap `_build_prompt` without touching any other method.

History window
--------------
`HISTORY_WINDOW` controls how many recent turns are included in the prompt.
Keeping it small avoids exceeding the model's context window.  A future
memory service will inject summarised long-term context here.
"""

import logging
from typing import Optional

from beanie import PydanticObjectId

from app.models.chat import ChatDocument, MessageRole
from app.models.user import UserDocument
from app.schemas.chat import ChatRequest, ChatHistoryItem
from app.services.llm_service import BaseLLMService

logger = logging.getLogger(__name__)

# Number of most-recent turns (user + assistant pairs) included in the prompt.
# Each "turn" = 2 messages, so 10 turns = up to 20 ChatDocument lookups.
HISTORY_WINDOW: int = 20  # individual messages (not pairs)

SYSTEM_PROMPT: str = (
    "You are a helpful, concise, and friendly AI assistant. "
    "Answer the user's questions clearly. "
    "If you don't know something, say so honestly."
)


class ChatService:
    """
    Orchestrates the full chat request/response lifecycle.

    Parameters
    ----------
    llm_service : BaseLLMService
        Injected LLM backend (real or mock).
    """

    def __init__(self, llm_service: BaseLLMService) -> None:
        self._llm = llm_service

    # ── Public API ─────────────────────────────────────────────────────────────

    async def chat(self, request: ChatRequest) -> str:
        """
        Process a user message end-to-end.

        Flow
        ----
        user message → save → load history → build prompt
            → generate → save assistant response → return

        Parameters
        ----------
        request : ChatRequest
            Validated request DTO (user_id + message text).

        Returns
        -------
        str
            The assistant's reply.

        Raises
        ------
        ValueError
            If user_id does not resolve to a known user.
        """
        await self._assert_user_exists(request.user_id)

        # 1. Persist the user's message.
        await self._save_message(
            user_id=request.user_id,
            role=MessageRole.USER,
            message=request.message,
        )
        logger.debug("Saved user message for user_id=%s", request.user_id)

        # 2. Load recent history (excludes the message we just saved so it
        #    doesn't appear twice in the prompt).
        history = await self._load_history(
            user_id=request.user_id,
            limit=HISTORY_WINDOW,
        )

        # 3. Build the full prompt.
        prompt = self._build_prompt(
            history=history,
            current_message=request.message,
        )
        logger.debug("Prompt built (%d chars).", len(prompt))

        # 4. Generate a response from the LLM.
        assistant_reply = await self._llm.generate(prompt)
        logger.debug("LLM response received (%d chars).", len(assistant_reply))

        # 5. Persist the assistant's response.
        await self._save_message(
            user_id=request.user_id,
            role=MessageRole.ASSISTANT,
            message=assistant_reply,
        )

        return assistant_reply

    async def get_history(
        self,
        user_id: str,
        limit: Optional[int] = None,
    ) -> list[ChatDocument]:
        """
        Return chronologically-ordered message history for a user.

        Parameters
        ----------
        user_id : str
            Target user's ObjectId hex string.
        limit : int | None
            Maximum number of messages to return.  None = all messages.
        """
        await self._assert_user_exists(user_id)
        return await self._load_history(user_id=user_id, limit=limit)

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    async def _assert_user_exists(user_id: str) -> UserDocument:
        """Raise ValueError if user_id is invalid or not found."""
        try:
            oid = PydanticObjectId(user_id)
        except Exception:
            raise ValueError(f"Invalid user_id format: '{user_id}'")

        user = await UserDocument.get(oid)
        if user is None:
            raise ValueError(f"User '{user_id}' not found.")
        return user

    @staticmethod
    async def _save_message(
        user_id: str,
        role: MessageRole,
        message: str,
    ) -> ChatDocument:
        """Create and persist a single ChatDocument."""
        doc = ChatDocument(user_id=user_id, role=role, message=message)
        await doc.insert()
        return doc

    @staticmethod
    async def _load_history(
        user_id: str,
        limit: Optional[int],
    ) -> list[ChatDocument]:
        """
        Load the N most recent messages for user_id, ordered oldest → newest.

        MongoDB sort is descending (newest first) then reversed in Python so
        the prompt reads naturally (oldest turn at the top).
        """
        query = ChatDocument.find(
            ChatDocument.user_id == user_id,
            sort=-ChatDocument.timestamp,  # newest first
        )
        if limit is not None:
            query = query.limit(limit)

        docs: list[ChatDocument] = await query.to_list()
        # Reverse to get chronological order (oldest at index 0)
        docs.reverse()
        return docs

    @staticmethod
    def _build_prompt(
        history: list[ChatDocument],
        current_message: str,
    ) -> str:
        """
        Assemble a text prompt from system instruction, history, and the
        current user message.

        Format
        ------
        System:
        <system prompt>

        Conversation History:
        User: <message>
        Assistant: <message>
        ...

        Current User Message:
        <current_message>

        Assistant:

        The trailing "Assistant:" cues most instruction-tuned models to
        generate an assistant-role continuation.

        Note: When using a tokenizer with `apply_chat_template` support,
        replace this method body with the template call.  The interface
        remains identical.
        """
        lines: list[str] = []

        # System block
        lines.append("System:")
        lines.append(SYSTEM_PROMPT)
        lines.append("")

        # History block (may be empty for first message)
        if history:
            lines.append("Conversation History:")
            for turn in history:
                role_label = "User" if turn.role == MessageRole.USER else "Assistant"
                lines.append(f"{role_label}: {turn.message}")
            lines.append("")

        # Current turn
        lines.append("Current User Message:")
        lines.append(current_message)
        lines.append("")
        lines.append("Assistant:")

        return "\n".join(lines)