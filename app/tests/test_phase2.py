import pytest
from unittest.mock import AsyncMock, MagicMock
from app.domain.memory_extractor import MemoryExtractor
from app.services.memory_service import MemoryService
from app.schemas.memory import UpsertMemoryRequest

# 1. MemoryExtractor Tests

import json

class FakeLLM:
    def __init__(self, structured_response: dict = None, raise_error: Exception = None):
        self.structured_response = structured_response
        self.raise_error = raise_error

    async def generate_structured(self, messages, schema, schema_name="structured_response"):
        if self.raise_error:
            raise self.raise_error
        return self.structured_response, 10


@pytest.mark.asyncio
async def test_extractor_returns_valid_memories():
    fake_response = {
        "memories": [
            {
                "key": "python_beginner",
                "value": "user is a beginner in python",
                "importance": 0.9,
                "confidence": 0.85,
                "memory_type": "skill_level",
                "topic": "python",
            }
        ]
    }
    extractor = MemoryExtractor(llm=FakeLLM(structured_response=fake_response))
    result = await extractor.extract(
        user_message="I am learning python and I am a beginner",
        assistant_response="Great! Let's start with the basics.",
    )
    assert len(result) == 1
    assert result[0]["key"] == "python_beginner"
    assert result[0]["memory_type"] == "skill_level"
    assert result[0]["topic"] == "python"
    assert 0.0 <= result[0]["importance"] <= 1.0
    assert 0.0 <= result[0]["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_extractor_returns_empty_on_no_content():
    extractor = MemoryExtractor(llm=FakeLLM(structured_response={"memories": []}))
    result = await extractor.extract(
        user_message="hello",
        assistant_response="hi there!",
    )
    assert result == []


@pytest.mark.asyncio
async def test_extractor_handles_invalid_json():
    error = json.JSONDecodeError("Expecting value", "doc", 0)
    extractor = MemoryExtractor(llm=FakeLLM(raise_error=error))
    result = await extractor.extract(
        user_message="hello",
        assistant_response="hi",
    )
    assert result == []


@pytest.mark.asyncio
async def test_extractor_handles_llm_failure():
    extractor = MemoryExtractor(llm=FakeLLM(raise_error=Exception("HTTP 503")))
    result = await extractor.extract("hello", "hi")
    assert result == []


@pytest.mark.asyncio
async def test_extractor_clamps_importance_and_confidence():
    fake_response = {
        "memories": [
            {
                "key": "test_key",
                "value": "test value",
                "importance": 99.9,
                "confidence": -5.0,
                "memory_type": "learning_topic",
                "topic": "test",
            }
        ]
    }
    extractor = MemoryExtractor(llm=FakeLLM(structured_response=fake_response))
    result = await extractor.extract("test", "test")
    assert result[0]["importance"] == 1.0
    assert result[0]["confidence"] == 0.0


@pytest.mark.asyncio
async def test_extractor_fixes_invalid_memory_type():
    fake_response = {
        "memories": [
            {
                "key": "test_key",
                "value": "test value",
                "importance": 0.5,
                "confidence": 0.5,
                "memory_type": "invalid_type_xyz",
                "topic": "test",
            }
        ]
    }
    extractor = MemoryExtractor(llm=FakeLLM(structured_response=fake_response))
    result = await extractor.extract("test", "test")
    assert result[0]["memory_type"] == "learning_topic"


@pytest.mark.asyncio
async def test_extractor_skips_items_without_key_or_value():
    fake_response = {
        "memories": [
            {"value": "no key here", "importance": 0.5},
            {"key": "no_value_here", "importance": 0.5},
            {
                "key": "valid_key", "value": "valid value", "importance": 0.7,
                "confidence": 0.8, "memory_type": "learning_topic", "topic": "test",
            },
        ]
    }
    extractor = MemoryExtractor(llm=FakeLLM(structured_response=fake_response))
    result = await extractor.extract("test", "test")
    assert len(result) == 1
    assert result[0]["key"] == "valid_key"
# 2. MemoryService Scoring Tests

class FakeMemory:
    def __init__(self, **kwargs):
        self.id = "fake_id_123"
        self.user_id = kwargs.get("user_id")
        self.key = kwargs.get("key")
        self.value = kwargs.get("value")
        self.importance = kwargs.get("importance", 0.5)
        self.confidence = kwargs.get("confidence", 0.8)
        self.memory_type = kwargs.get("memory_type", "learning_topic")
        self.topic = kwargs.get("topic", "general")
        self.frequency = kwargs.get("frequency", 1)
        self.source_session_id = kwargs.get("source_session_id")
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        self.created_at = now
        self.updated_at = now
        self.last_accessed_at = now


def test_memory_response_includes_scoring_fields():
    from app.schemas.memory import MemoryResponse
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    response = MemoryResponse(
        id="abc123",
        user_id="user1",
        key="python_skill",
        value="beginner",
        importance=0.8,
        memory_type="skill_level",
        topic="python",
        frequency=3,
        confidence=0.9,
        created_at=now,
        updated_at=now,
    )
    assert response.frequency == 3
    assert response.confidence == 0.9


def test_upsert_request_defaults():
    req = UpsertMemoryRequest(key="test_key", value="test value")
    assert req.importance == 0.5
    assert req.memory_type == "learning_topic"
    assert req.topic is None


def test_upsert_request_importance_bounds():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UpsertMemoryRequest(key="k", value="v", importance=1.5)

    with pytest.raises(ValidationError):
        UpsertMemoryRequest(key="k", value="v", importance=-0.1)