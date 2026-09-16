# tests/test_phase7.py
import pytest
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock, MagicMock

from app.domain.chunker import chunk_text
from app.domain.session_summarizer import SessionSummarizer
from app.domain.prompt_builder import PromptBuilder
from app.repositories.chat_repository import ChatRepository


# ---------------------------------------------------------------------------
# FakeLLM (same shape as used in test_phase6.py / test_quiz_workflow.py)
# ---------------------------------------------------------------------------

class FakeLLM:
    def __init__(self, structured_response: dict = None, raise_error: Exception = None):
        self.structured_response = structured_response
        self.raise_error = raise_error
        self.last_messages = None
        self.last_schema_name = None

    async def generate_structured(self, messages, schema, schema_name="structured_response", max_tokens=1500):
        self.last_messages = messages
        self.last_schema_name = schema_name
        if self.raise_error:
            raise self.raise_error
        return self.structured_response, 42


# ---------------------------------------------------------------------------
# chunker.chunk_text
# ---------------------------------------------------------------------------

class TestChunkText:

    def test_empty_text_returns_no_chunks(self):
        assert chunk_text("") == []

    def test_whitespace_only_returns_no_chunks(self):
        assert chunk_text("   \n  ") == []

    def test_text_shorter_than_chunk_size_returns_single_chunk(self):
        result = chunk_text("hello world", chunk_size=800, overlap=100)
        assert result == ["hello world"]

    def test_text_exactly_chunk_size_returns_single_chunk(self):
        text = "a" * 800
        result = chunk_text(text, chunk_size=800, overlap=100)
        assert len(result) == 1
        assert len(result[0]) == 800

    def test_long_text_splits_with_overlap(self):
        text = "x" * 250
        result = chunk_text(text, chunk_size=100, overlap=20)
        assert len(result) == 3
        assert [len(c) for c in result] == [100, 100, 90]

    def test_consecutive_chunks_actually_overlap(self):
        # Build text where each 10-char block is uniquely identifiable
        text = "".join(f"{i:04d}" for i in range(50))  # 200 chars
        result = chunk_text(text, chunk_size=50, overlap=10)
        # end of chunk N should reappear at the start of chunk N+1
        assert result[0][-10:] == result[1][:10]


# ---------------------------------------------------------------------------
# SessionSummarizer
# ---------------------------------------------------------------------------

class TestSessionSummarizerTrigger:

    def test_should_not_summarize_below_threshold(self):
        summarizer = SessionSummarizer(llm=FakeLLM())
        assert summarizer.should_summarize(message_count=8, last_summarized_count=0) is False

    def test_should_summarize_at_exact_threshold(self):
        summarizer = SessionSummarizer(llm=FakeLLM())
        assert summarizer.should_summarize(message_count=10, last_summarized_count=0) is True

    def test_should_summarize_past_threshold(self):
        summarizer = SessionSummarizer(llm=FakeLLM())
        assert summarizer.should_summarize(message_count=25, last_summarized_count=14) is True

    def test_should_not_summarize_right_after_previous_summary(self):
        summarizer = SessionSummarizer(llm=FakeLLM())
        assert summarizer.should_summarize(message_count=22, last_summarized_count=14) is False


class TestSessionSummarizerSummarize:

    @pytest.mark.asyncio
    async def test_summarize_returns_llm_generated_text(self):
        fake_response = {"summary": "Student covered decorators and async/await."}
        llm = FakeLLM(structured_response=fake_response)
        summarizer = SessionSummarizer(llm=llm)

        recent = [
            {"role": "user", "content": "what is a decorator?"},
            {"role": "assistant", "content": "a function that wraps another function"},
        ]

        summary, tokens = await summarizer.summarize(previous_summary=None, recent_messages=recent)

        assert summary == "Student covered decorators and async/await."
        assert tokens == 42
        assert llm.last_schema_name == "session_summary"

    @pytest.mark.asyncio
    async def test_summarize_includes_previous_summary_in_prompt(self):
        llm = FakeLLM(structured_response={"summary": "merged summary"})
        summarizer = SessionSummarizer(llm=llm)

        await summarizer.summarize(
            previous_summary="Student is learning decorators.",
            recent_messages=[{"role": "user", "content": "now explain async/await"}],
        )

        prompt_text = llm.last_messages[0]["content"]
        assert "Student is learning decorators." in prompt_text
        assert "now explain async/await" in prompt_text

    @pytest.mark.asyncio
    async def test_summarize_handles_no_previous_summary_gracefully(self):
        llm = FakeLLM(structured_response={"summary": "first summary"})
        summarizer = SessionSummarizer(llm=llm)

        await summarizer.summarize(previous_summary=None, recent_messages=[{"role": "user", "content": "hi"}])

        prompt_text = llm.last_messages[0]["content"]
        assert "(none yet)" in prompt_text


# ---------------------------------------------------------------------------
# ChatRepository.get_messages — regression test for the sort-order bug fix
# (was returning the OLDEST `limit` messages instead of the most recent ones)
# ---------------------------------------------------------------------------

class TestChatRepositoryMessageOrdering:

    @pytest.mark.asyncio
    async def test_get_messages_returns_most_recent_n_in_chronological_order(self):
        # Simulates what Mongo gives back when sorted -created_at, limit=3:
        # newest first.
        newest_first = [
            SimpleNamespace(content="msg_20"),
            SimpleNamespace(content="msg_19"),
            SimpleNamespace(content="msg_18"),
        ]

        fake_chain = SimpleNamespace(
            sort=MagicMock(return_value=SimpleNamespace(
                limit=MagicMock(return_value=SimpleNamespace(
                    to_list=AsyncMock(return_value=newest_first)
                ))
            ))
        )

        with patch("app.repositories.chat_repository.Message") as MockMessage:
            MockMessage.find.return_value = fake_chain

            repo = ChatRepository()
            result = await repo.get_messages("session_1", limit=3)

        # Must come back oldest -> newest for correct prompt ordering
        assert [m.content for m in result] == ["msg_18", "msg_19", "msg_20"]

    @pytest.mark.asyncio
    async def test_get_messages_empty_session_returns_empty_list(self):
        fake_chain = SimpleNamespace(
            sort=MagicMock(return_value=SimpleNamespace(
                limit=MagicMock(return_value=SimpleNamespace(
                    to_list=AsyncMock(return_value=[])
                ))
            ))
        )

        with patch("app.repositories.chat_repository.Message") as MockMessage:
            MockMessage.find.return_value = fake_chain

            repo = ChatRepository()
            result = await repo.get_messages("session_1", limit=20)

        assert result == []


# ---------------------------------------------------------------------------
# DocumentService.search — relevance threshold wiring
# ---------------------------------------------------------------------------

class TestDocumentServiceRelevanceThreshold:

    @pytest.mark.asyncio
    async def test_search_passes_configured_threshold_to_qdrant(self):
        from app.services.document_service import DocumentService

        fake_settings = SimpleNamespace(
            qdrant_document_collection_name="document_chunks",
            document_relevance_threshold=0.35,
        )
        fake_embedding_service = SimpleNamespace(embed=AsyncMock(return_value=[0.1, 0.2, 0.3]))
        fake_client = SimpleNamespace(
            query_points=AsyncMock(return_value=SimpleNamespace(points=[]))
        )

        with patch("app.services.document_service.get_settings", return_value=fake_settings), \
             patch("app.services.document_service.get_embedding_service", return_value=fake_embedding_service), \
             patch("app.services.document_service.get_qdrant_client", return_value=fake_client):

            service = DocumentService()
            await service.search(user_id="u1", query_text="async await", limit=5)

        _, kwargs = fake_client.query_points.call_args
        assert kwargs["score_threshold"] == 0.35

    @pytest.mark.asyncio
    async def test_search_returns_empty_list_when_nothing_clears_threshold(self):
        from app.services.document_service import DocumentService

        fake_settings = SimpleNamespace(
            qdrant_document_collection_name="document_chunks",
            document_relevance_threshold=0.35,
        )
        fake_embedding_service = SimpleNamespace(embed=AsyncMock(return_value=[0.1, 0.2, 0.3]))
        # Qdrant applies score_threshold server-side; simulate it filtering everything out
        fake_client = SimpleNamespace(
            query_points=AsyncMock(return_value=SimpleNamespace(points=[]))
        )

        with patch("app.services.document_service.get_settings", return_value=fake_settings), \
             patch("app.services.document_service.get_embedding_service", return_value=fake_embedding_service), \
             patch("app.services.document_service.get_qdrant_client", return_value=fake_client):

            service = DocumentService()
            result = await service.search(user_id="u1", query_text="unrelated topic", limit=5)

        assert result == []

    @pytest.mark.asyncio
    async def test_search_maps_qdrant_points_to_document_chunk_results(self):
        from app.services.document_service import DocumentService

        fake_settings = SimpleNamespace(
            qdrant_document_collection_name="document_chunks",
            document_relevance_threshold=0.35,
        )
        fake_embedding_service = SimpleNamespace(embed=AsyncMock(return_value=[0.1, 0.2, 0.3]))
        fake_point = SimpleNamespace(
            payload={
                "document_id": "doc1",
                "filename": "notes.pdf",
                "text": "async/await lets you write non-blocking code",
            },
            score=0.81,
        )
        fake_client = SimpleNamespace(
            query_points=AsyncMock(return_value=SimpleNamespace(points=[fake_point]))
        )

        with patch("app.services.document_service.get_settings", return_value=fake_settings), \
             patch("app.services.document_service.get_embedding_service", return_value=fake_embedding_service), \
             patch("app.services.document_service.get_qdrant_client", return_value=fake_client):

            service = DocumentService()
            result = await service.search(user_id="u1", query_text="async await", limit=5)

        assert len(result) == 1
        assert result[0].filename == "notes.pdf"
        assert result[0].score == 0.81

    @pytest.mark.asyncio
    async def test_search_returns_empty_list_on_qdrant_failure(self):
        from app.services.document_service import DocumentService

        fake_settings = SimpleNamespace(
            qdrant_document_collection_name="document_chunks",
            document_relevance_threshold=0.35,
        )
        fake_embedding_service = SimpleNamespace(embed=AsyncMock(side_effect=Exception("Qdrant down")))
        fake_client = SimpleNamespace(query_points=AsyncMock())

        with patch("app.services.document_service.get_settings", return_value=fake_settings), \
             patch("app.services.document_service.get_embedding_service", return_value=fake_embedding_service), \
             patch("app.services.document_service.get_qdrant_client", return_value=fake_client):

            service = DocumentService()
            result = await service.search(user_id="u1", query_text="async await", limit=5)

        assert result == []


# ---------------------------------------------------------------------------
# PromptBuilder — session_summary injection
# ---------------------------------------------------------------------------

class TestPromptBuilderContinuitySummary:

    def test_session_summary_injected_into_system_prompt(self):
        messages = PromptBuilder.build(
            [], "hello", session_summary="Student has covered loops and functions."
        )
        system = messages[0]["content"]
        assert "Ongoing Learning Journey" in system
        assert "Student has covered loops and functions." in system

    def test_no_session_summary_no_continuity_section(self):
        messages = PromptBuilder.build([], "hello", session_summary=None)
        system = messages[0]["content"]
        assert "Ongoing Learning Journey" not in system

    def test_empty_string_session_summary_no_continuity_section(self):
        messages = PromptBuilder.build([], "hello", session_summary="")
        system = messages[0]["content"]
        assert "Ongoing Learning Journey" not in system