import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.schemas.learning_profile import LearningProfileSummary
from app.services.chat_service import ChatService


class FakeRepository:
    def __init__(self, message_count: int = 0):
        self.messages = []
        self.updated_sessions = []
        self.session = SimpleNamespace(
            id="session1",
            user_id="user123",
            message_count=message_count,
            title="New Chat",
            summary=None,
            last_summarized_message_count=0,
        )

    async def get_or_create_latest_session(self, user_id: str):
        return self.session

    async def create_message(self, session_id, role, content, tokens_used=None):
        message = SimpleNamespace(
            id=f"msg{len(self.messages) + 1}",
            session_id=session_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
        )
        self.messages.append(message)
        return message
    async def get_messages(self, session_id: str, limit: int = 20):
        return self.messages[-limit:]

    async def update_session(self, session):
        self.updated_sessions.append(session)
        return session


class FakeLLM:
    def __init__(self, content: str = "سلام، من پاسخ تستی هستم", tokens: int = 15):
        self.content = content
        self.tokens = tokens
        self.generate_with_tools_calls = []
        self.generate_calls = []

    async def generate_with_tools(self, messages, tools):
        self.generate_with_tools_calls.append({"messages": messages, "tools": tools})
        return {
            "content": self.content,
            "tool_calls": [],
            "tokens": self.tokens,
        }

    async def generate(self, messages):
        self.generate_calls.append(messages)
        return "fallback", 5


class FakeMemoryService:
    def __init__(self, similar=None, listed=None):
        self.similar = similar or []
        self.listed = listed or []
        self.upserts = []
        self.search_queries = []

    async def search_similar(self, user_id, query_text, limit=5):
        self.search_queries.append(query_text)
        return self.similar

    async def list_memories(self, user_id, min_importance=0.0):
        return self.listed

    async def upsert(self, user_id, payload, source_session_id=None):
        self.upserts.append({
            "user_id": user_id,
            "payload": payload,
            "source_session_id": source_session_id,
        })
        return payload


class FakeMemoryExtractor:
    def __init__(self, memories=None):
        self.memories = memories or []
        self.calls = []

    async def extract(self, user_message, assistant_response):
        self.calls.append((user_message, assistant_response))
        return self.memories


class FakeDocumentService:
    def __init__(self, chunks=None):
        self.chunks = chunks or []
        self.queries = []

    async def search(self, user_id, query_text, limit=5):
        self.queries.append(query_text)
        return self.chunks


class FakeProfileService:
    def __init__(self, summary=None):
        self.summary = summary or LearningProfileSummary(
            user_id="user123",
            topics={},
            preferred_style=None,
        )
        self.calls = []

    async def get_summary(self, user_id):
        self.calls.append(user_id)
        return self.summary


class FakeSummarizer:
    SUMMARIZE_EVERY_N_MESSAGES = 10

    def __init__(self, should: bool = False, summary: str = "rolling summary"):
        self._should = should
        self.summary = summary
        self.summarize_calls = []

    def should_summarize(self, message_count, last_summarized_count):
        return self._should

    async def summarize(self, previous_summary, recent_messages):
        self.summarize_calls.append((previous_summary, recent_messages))
        return self.summary, 8


def make_service(
    repo=None,
    llm=None,
    memory_service=None,
    memory_extractor=None,
    document_service=None,
    profile_service=None,
    summarizer=None,
):
    return ChatService(
        repo=repo or FakeRepository(),
        llm=llm or FakeLLM(),
        memory_service=memory_service or FakeMemoryService(),
        memory_extractor=memory_extractor or FakeMemoryExtractor(),
        document_service=document_service or FakeDocumentService(),
        profile_service=profile_service or FakeProfileService(),
        summarizer=summarizer or FakeSummarizer(should=False),
    )


@pytest.mark.asyncio
async def test_send_message():
    repo = FakeRepository()
    llm = FakeLLM()
    service = make_service(repo=repo, llm=llm)

    result = await service.send_message(
        user_id="user123",
        content="سلام",
    )

    assert result["assistant_message"].content == "سلام، من پاسخ تستی هستم"
    assert result["assistant_message"].tokens_used == 15
    assert result["session_id"] == "session1"
    assert len(repo.messages) == 2
    assert repo.messages[0].role == "user"
    assert repo.messages[0].content == "سلام"
    assert repo.messages[1].role == "assistant"
    assert repo.session.message_count == 2
    assert repo.session.title == "سلام"
    assert len(llm.generate_with_tools_calls) == 1


@pytest.mark.asyncio
async def test_send_message_falls_back_to_list_memories_when_search_empty():
    listed = [SimpleNamespace(key="python_level", value="beginner")]
    memory_service = FakeMemoryService(similar=[], listed=listed)
    service = make_service(memory_service=memory_service)

    await service.send_message(user_id="user123", content="python loops")

    assert memory_service.search_queries == ["python loops"]


@pytest.mark.asyncio
async def test_send_message_uses_semantic_memories_when_found():
    similar = [SimpleNamespace(key="python_weak", value="recursion")]
    memory_service = FakeMemoryService(similar=similar, listed=[])
    service = make_service(memory_service=memory_service)

    await service.send_message(user_id="user123", content="help with recursion")

    assert memory_service.search_queries == ["help with recursion"]


@pytest.mark.asyncio
async def test_send_message_extracts_and_upserts_memories():
    extractor = FakeMemoryExtractor(memories=[
        {
            "key": "python_beginner",
            "value": "user is a beginner in python",
            "importance": 0.9,
            "memory_type": "skill_level",
            "topic": "python",
        }
    ])
    memory_service = FakeMemoryService()
    service = make_service(
        memory_service=memory_service,
        memory_extractor=extractor,
    )

    await service.send_message(user_id="user123", content="I am new to python")

    assert len(extractor.calls) == 1
    assert extractor.calls[0][0] == "I am new to python"
    assert len(memory_service.upserts) == 1
    upsert = memory_service.upserts[0]
    assert upsert["user_id"] == "user123"
    assert upsert["source_session_id"] == "session1"
    assert upsert["payload"].key == "python_beginner"
    assert upsert["payload"].importance == 0.9


@pytest.mark.asyncio
async def test_send_message_does_not_fail_when_memory_extraction_errors():
    extractor = FakeMemoryExtractor()
    extractor.extract = AsyncMock(side_effect=RuntimeError("llm down"))
    service = make_service(memory_extractor=extractor)

    result = await service.send_message(user_id="user123", content="سلام")

    assert result["assistant_message"].content == "سلام، من پاسخ تستی هستم"


@pytest.mark.asyncio
async def test_send_message_does_not_auto_title_after_first_turn():
    repo = FakeRepository(message_count=4)
    service = make_service(repo=repo)

    await service.send_message(user_id="user123", content="explain decorators")

    assert repo.session.title == "New Chat"
    assert repo.session.message_count == 6


@pytest.mark.asyncio
async def test_send_message_loads_profile_and_documents():
    profile_service = FakeProfileService()
    document_service = FakeDocumentService()
    service = make_service(
        profile_service=profile_service,
        document_service=document_service,
    )

    await service.send_message(user_id="user123", content="what is a list?")

    assert profile_service.calls == ["user123"]
    assert document_service.queries == ["what is a list?"]


@pytest.mark.asyncio
async def test_send_message_skips_summary_below_threshold():
    summarizer = FakeSummarizer(should=False)
    repo = FakeRepository()
    service = make_service(repo=repo, summarizer=summarizer)

    await service.send_message(user_id="user123", content="سلام")

    assert summarizer.summarize_calls == []
    assert repo.session.summary is None


@pytest.mark.asyncio
async def test_send_message_refreshes_summary_when_due():
    summarizer = FakeSummarizer(should=True, summary="covered python basics")
    repo = FakeRepository()
    service = make_service(repo=repo, summarizer=summarizer)

    await service.send_message(user_id="user123", content="سلام")

    assert len(summarizer.summarize_calls) == 1
    assert repo.session.summary == "covered python basics"
    assert repo.session.last_summarized_message_count == 2