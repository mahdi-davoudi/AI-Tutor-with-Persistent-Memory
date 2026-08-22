from app.repositories.chat_repository import ChatRepository
from app.services.profile_service import ProfileService
from app.domain.session_policy import SessionPolicy
from app.domain.prompt_builder import PromptBuilder
from app.domain.tool_executor import ToolExecutor
from app.models.chat import Message, ChatSession
from app.services.llm_service import LLMService
from app.domain.tools import AVAILABLE_TOOLS
from datetime import datetime, timezone
import json



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
        try:
            memories = await self.memory_extractor.extract(
                user_message=user_message,
                assistant_response=answer,
            )

            print("=" * 50)
            print("EXTRACTED MEMORIES:", memories)
            print("=" * 50)

            from app.schemas.memory import UpsertMemoryRequest

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
                except Exception as e:
                    print(f"MEMORY UPSERT ERROR: {e}")
                    continue

        except Exception as e:
            print(f"MEMORY EXTRACTION ERROR: {e}")
            import traceback
            traceback.print_exc()


    MAX_TOOL_ITERATIONS = 3
    async def _generate_with_tools(self, messages: list[dict], user_id: str) -> tuple[str, int]:
        executor = ToolExecutor(user_id=user_id)
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

        # 1. Get or create session
        session = await self._get_or_create_session(user_id)
        session_id = str(session.id)
        print(f"SESSION ID: {session_id}")

        # 2. Save user message
        user_msg = Message(
            session_id=session_id,
            role="user",
            content=content,
        )
        await self.repo.create_message(user_msg)
        print(f"USER MSG SAVED: {user_msg.id}")

        # 3. Get history
        history = await self.repo.get_messages(session_id, limit=20)
        history_dict = [
            {"role": m.role, "content": m.content}
            for m in history
        ]

        # 4. Load memories
        memories = await self.memory_service.list_memories(user_id)

        # 4.5 Load learning profile 
        profile = await ProfileService().get_summary(user_id)

        # 5. Build prompt 
        messages = PromptBuilder.build(history_dict, content, memories, profile)

        # 6. Call LLM
        answer, tokens = await self._generate_with_tools(messages, user_id=user_id)
        
        # 7. Save assistant message
        assistant_msg = Message(
            session_id=session_id,
            role="assistant",
            content=answer,
            tokens_used=tokens,
        )
        await self.repo.create_message(assistant_msg)

        # 8. Extract and store memories
        await self._extract_and_store_memories(
            user_id=user_id,
            session_id=session_id,
            user_message=content,
            answer=answer,
        )

        # 9. Update session metadata
        new_count = session.message_count + 2
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
        print(f"SESSION UPDATED: {session.id}, message_count={session.message_count}, title={session.title}")

        # 10. Return response
        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "session_id": session_id,
        }