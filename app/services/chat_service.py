import json
import logging
from datetime import datetime, timezone
from app.domain.prompt_builder import PromptBuilder
from app.domain.session_policy import SessionPolicy
from app.domain.session_summarizer import SessionSummarizer
from app.domain.tool_executor import ToolExecutor
from app.domain.tools import AVAILABLE_TOOLS
from app.models.chat import ChatSession
from app.repositories.chat_repository import ChatRepository
from app.schemas.memory import UpsertMemoryRequest
from app.services.document_service import DocumentService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.profile_service import ProfileService

logger = logging.getLogger(__name__)


class ChatService:
    MAX_TOOL_ITERATIONS = 3

    def __init__(
        self,
        repo: ChatRepository,
        llm: LLMService,
        memory_service: MemoryService,
        memory_extractor,
        document_service: DocumentService,
        profile_service: ProfileService,
        summarizer: SessionSummarizer | None = None,
    ):
        self.repo = repo
        self.llm = llm
        self.memory_service = memory_service
        self.memory_extractor = memory_extractor
        self.document_service = document_service
        self.profile_service = profile_service
        self.summarizer = summarizer or SessionSummarizer(llm)

    async def _get_or_create_session(self, user_id: str) -> ChatSession:
        return await self.repo.get_or_create_latest_session(user_id)

    async def _extract_and_store_memories(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        answer: str,
    ) -> None:
        try:
            memories = await self.memory_extractor.extract(
                user_message=user_message,
                assistant_response=answer,
            )
            logger.debug("extracted memories: %s", memories)

            for memory in memories:
                try:
                    payload = UpsertMemoryRequest(
                        key=memory["key"],
                        value=memory["value"],
                        importance=memory.get("importance", 0.5),
                        memory_type=memory.get("memory_type", "learning_topic"),
                        topic=memory.get("topic", "general"),
                    )
                    await self.memory_service.upsert(
                        user_id=user_id,
                        payload=payload,
                        source_session_id=session_id,
                    )
                except Exception:
                    logger.exception("memory upsert failed for key=%s", memory.get("key"))
                    continue
        except Exception:
            logger.exception("memory extraction failed for user_id=%s", user_id)

    async def _generate_with_tools(
        self,
        messages: list[dict],
        user_id: str,
    ) -> tuple[str, int]:
        executor = ToolExecutor(
            user_id=user_id,
            profile_service=self.profile_service,
        )
        total_tokens = 0
        working_messages = list(messages)

        for _ in range(self.MAX_TOOL_ITERATIONS):
            result = await self.llm.generate_with_tools(
                messages=working_messages,
                tools=AVAILABLE_TOOLS,
            )
            total_tokens += result["tokens"]

            tool_calls = result["tool_calls"]
            if not tool_calls:
                return result["content"] or "", total_tokens

            working_messages.append({
                "role": "assistant",
                "content": result["content"],
                "tool_calls": tool_calls,
            })

            for call in tool_calls:
                fn_name = call["function"]["name"]
                try:
                    fn_args = json.loads(call["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    fn_args = {}

                tool_result = await executor.execute(fn_name, fn_args)
                working_messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": tool_result,
                })

        answer, tokens = await self.llm.generate(working_messages)
        return answer, total_tokens + tokens

    async def send_message(self, user_id: str, content: str):
        session = await self._get_or_create_session(user_id)
        session_id = str(session.id)
        logger.debug("session_id=%s user_id=%s", session_id, user_id)

        user_msg = await self.repo.create_message(
            session_id=session_id,
            role="user",
            content=content,
        )
        
        history = await self.repo.get_messages(session_id, limit=20)
        history_dict = [{"role": m.role, "content": m.content} for m in history]

        memories = await self.memory_service.search_similar(user_id, content, limit=5)
        if not memories:
            memories = await self.memory_service.list_memories(user_id, min_importance=0.5)

        profile = await self.profile_service.get_summary(user_id)
        document_chunks = await self.document_service.search(user_id, content, limit=3)
        session_summary = session.summary

        messages = PromptBuilder.build(
            history_dict,
            content,
            memories,
            profile,
            document_chunks,
            session_summary,
        )
        logger.debug("system prompt: %s", messages[0]["content"])

        answer, tokens = await self._generate_with_tools(messages, user_id=user_id)

        assistant_msg = await self.repo.create_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            tokens_used=tokens,
        )
        
        await self._extract_and_store_memories(
            user_id=user_id,
            session_id=session_id,
            user_message=content,
            answer=answer,
        )

        new_count = session.message_count + 2
        session.message_count = new_count
        session.updated_at = datetime.now(timezone.utc)

        if SessionPolicy.should_auto_title(session.message_count - 2):
            session.title = SessionPolicy.generate_title(content)

        await self.repo.update_session(session)
        logger.info(
            "session updated id=%s message_count=%s title=%s",
            session.id,
            session.message_count,
            session.title,
        )

        if self.summarizer.should_summarize(
            session.message_count,
            session.last_summarized_message_count,
        ):
            try:
                recent = await self.repo.get_messages(
                    session_id,
                    limit=self.summarizer.SUMMARIZE_EVERY_N_MESSAGES,
                )
                recent_dict = [{"role": m.role, "content": m.content} for m in recent]
                new_summary, _ = await self.summarizer.summarize(session.summary, recent_dict)

                session.summary = new_summary
                session.summary_updated_at = datetime.now(timezone.utc)
                session.last_summarized_message_count = session.message_count
                await self.repo.update_session(session)
                logger.info("session summary updated id=%s", session.id)
            except Exception:
                logger.exception("session summary failed id=%s", session.id)

        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "session_id": session_id,
        }