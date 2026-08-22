import pytest
from app.domain.recommendation_engine import RecommendationEngine
import json
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
from app.domain.tool_executor import ToolExecutor
from app.services.chat_service import ChatService

class FakeLLM:
    def __init__(self, structured_response: dict = None, raise_error: Exception = None):
        self.structured_response = structured_response
        self.raise_error = raise_error

    async def generate_structured(self, messages, schema, schema_name="structured_response"):
        if self.raise_error:
            raise self.raise_error
        return self.structured_response, 10


@pytest.mark.asyncio
async def test_recommendation_returns_structured_data():
    fake_response = {
        "suggested_topics": ["recursion", "decorators", "generators"],
        "weak_areas": ["recursion"],
        "learning_path": ["review basics", "practice recursion", "build a project"],
        "reasoning": "User struggles with recursion based on recent memory notes.",
    }
    engine = RecommendationEngine(llm_service=FakeLLM(structured_response=fake_response))

    result = await engine.generate(
        learning_profile={"user_id": "u1", "python": {"mastery": 0.4}},
        memories=[{"content": "struggles with recursion base cases"}],
    )

    assert result["suggested_topics"] == ["recursion", "decorators", "generators"]
    assert result["weak_areas"] == ["recursion"]
    assert len(result["learning_path"]) == 3
    assert "recursion" in result["reasoning"]


@pytest.mark.asyncio
async def test_recommendation_handles_empty_profile_and_memories():
    fake_response = {
        "suggested_topics": [],
        "weak_areas": [],
        "learning_path": [],
        "reasoning": "Not enough data yet to generate a recommendation.",
    }
    engine = RecommendationEngine(llm_service=FakeLLM(structured_response=fake_response))

    result = await engine.generate(learning_profile={}, memories=[])

    assert result["suggested_topics"] == []
    assert result["weak_areas"] == []
    assert result["learning_path"] == []


@pytest.mark.asyncio
async def test_recommendation_handles_llm_failure_gracefully():
    engine = RecommendationEngine(llm_service=FakeLLM(raise_error=Exception("LLM timeout")))

    result = await engine.generate(
        learning_profile={"python": {"mastery": 0.5}},
        memories=[],
    )

    assert result["suggested_topics"] == []
    assert result["weak_areas"] == []
    assert result["learning_path"] == []
    assert result["reasoning"] is None


@pytest.mark.asyncio
async def test_recommendation_handles_malformed_llm_response():
  
    fake_response = {"suggested_topics": ["loops"]}
    engine = RecommendationEngine(llm_service=FakeLLM(structured_response=fake_response))

    result = await engine.generate(learning_profile={}, memories=[])

    assert result["suggested_topics"] == ["loops"]
    assert result["weak_areas"] == []
    assert result["learning_path"] == []
    
def make_fake_summary(topics: dict):
    return SimpleNamespace(topics=topics)


@pytest.mark.asyncio
async def test_get_learning_progress_found():
    fake_topic = SimpleNamespace(
        mastery=0.7, level="intermediate", strong=["variables"], weak=["recursion"]
    )
    fake_summary = make_fake_summary({"python": fake_topic})

    with patch("app.domain.tool_executor.ProfileService") as MockProfileService:
        MockProfileService.return_value.get_summary = AsyncMock(return_value=fake_summary)

        executor = ToolExecutor(user_id="u1")
        result = json.loads(await executor.execute("get_learning_progress", {"topic": "Python"}))

    assert result["found"] is True
    assert result["topic"] == "python"
    assert result["mastery"] == 0.7
    assert result["weak"] == ["recursion"]


@pytest.mark.asyncio
async def test_get_learning_progress_not_found():
    fake_summary = make_fake_summary({})

    with patch("app.domain.tool_executor.ProfileService") as MockProfileService:
        MockProfileService.return_value.get_summary = AsyncMock(return_value=fake_summary)

        executor = ToolExecutor(user_id="u1")
        result = json.loads(await executor.execute("get_learning_progress", {"topic": "rust"}))

    assert result["found"] is False
    assert result["topic"] == "rust"


@pytest.mark.asyncio
async def test_list_weak_areas_filters_only_weak_topics():
    weak_topic = SimpleNamespace(mastery=0.3, level="beginner", strong=[], weak=["loops"])
    strong_topic = SimpleNamespace(mastery=0.9, level="advanced", strong=["oop"], weak=[])
    fake_summary = make_fake_summary({"python": weak_topic, "sql": strong_topic})

    with patch("app.domain.tool_executor.ProfileService") as MockProfileService:
        MockProfileService.return_value.get_summary = AsyncMock(return_value=fake_summary)

        executor = ToolExecutor(user_id="u1")
        result = json.loads(await executor.execute("list_weak_areas", {}))

    assert len(result["weak_areas"]) == 1
    assert result["weak_areas"][0]["topic"] == "python"
    assert result["weak_areas"][0]["weak_skills"] == ["loops"]


@pytest.mark.asyncio
async def test_unknown_tool_returns_error():
    executor = ToolExecutor(user_id="u1")
    result = json.loads(await executor.execute("delete_everything", {}))
    assert "error" in result


@pytest.mark.asyncio
async def test_tool_executor_handles_service_exception():
    with patch("app.domain.tool_executor.ProfileService") as MockProfileService:
        MockProfileService.return_value.get_summary = AsyncMock(side_effect=Exception("DB down"))

        executor = ToolExecutor(user_id="u1")
        result = json.loads(await executor.execute("get_learning_progress", {"topic": "python"}))

    assert "error" in result
    
    
class FakeLLMWithTools:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def generate_with_tools(self, messages, tools):
        self.calls.append(messages)
        return self.responses.pop(0)

    async def generate(self, messages):
        return "fallback answer", 5


@pytest.mark.asyncio
async def test_generate_with_tools_no_tool_call_returns_directly():
    fake_llm = FakeLLMWithTools([
        {"content": "Hello! I can help with that.", "tool_calls": [], "tokens": 20},
    ])
    service = ChatService(repo=None, llm=fake_llm, memory_service=None, memory_extractor=None)

    answer, tokens = await service._generate_with_tools(
        messages=[{"role": "user", "content": "hi"}], user_id="u1",
    )

    assert answer == "Hello! I can help with that."
    assert tokens == 20
    assert len(fake_llm.calls) == 1


@pytest.mark.asyncio
async def test_generate_with_tools_executes_tool_and_returns_final_answer():
    tool_call = {
        "id": "call_1",
        "function": {"name": "get_learning_progress", "arguments": '{"topic": "python"}'},
    }
    fake_llm = FakeLLMWithTools([
        {"content": None, "tool_calls": [tool_call], "tokens": 15},
        {"content": "You're intermediate in python.", "tool_calls": [], "tokens": 25},
    ])
    fake_tool_result = json.dumps({"topic": "python", "found": True, "mastery": 0.6})

    with patch("app.services.chat_service.ToolExecutor") as MockExecutor:
        MockExecutor.return_value.execute = AsyncMock(return_value=fake_tool_result)

        service = ChatService(repo=None, llm=fake_llm, memory_service=None, memory_extractor=None)
        answer, tokens = await service._generate_with_tools(
            messages=[{"role": "user", "content": "how am I doing in python?"}], user_id="u1",
        )

    assert answer == "You're intermediate in python."
    assert tokens == 40
    assert len(fake_llm.calls) == 2

    second_call_messages = fake_llm.calls[1]
    tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["content"] == fake_tool_result
    assert tool_messages[0]["tool_call_id"] == "call_1"


@pytest.mark.asyncio
async def test_generate_with_tools_handles_invalid_arguments_json():
    tool_call = {
        "id": "call_1",
        "function": {"name": "list_weak_areas", "arguments": "not-valid-json"},
    }
    fake_llm = FakeLLMWithTools([
        {"content": None, "tool_calls": [tool_call], "tokens": 10},
        {"content": "Here's your weak areas.", "tool_calls": [], "tokens": 10},
    ])

    with patch("app.services.chat_service.ToolExecutor") as MockExecutor:
        MockExecutor.return_value.execute = AsyncMock(return_value=json.dumps({"weak_areas": []}))

        service = ChatService(repo=None, llm=fake_llm, memory_service=None, memory_extractor=None)
        answer, tokens = await service._generate_with_tools(
            messages=[{"role": "user", "content": "what are my weak areas?"}], user_id="u1",
        )

    MockExecutor.return_value.execute.assert_called_once_with("list_weak_areas", {})
    assert answer == "Here's your weak areas."


@pytest.mark.asyncio
async def test_generate_with_tools_hits_max_iterations_and_falls_back():
    tool_call = {
        "id": "call_x",
        "function": {"name": "list_weak_areas", "arguments": "{}"},
    }
    fake_llm = FakeLLMWithTools([
        {"content": None, "tool_calls": [tool_call], "tokens": 10},
        {"content": None, "tool_calls": [tool_call], "tokens": 10},
        {"content": None, "tool_calls": [tool_call], "tokens": 10},
    ])

    with patch("app.services.chat_service.ToolExecutor") as MockExecutor:
        MockExecutor.return_value.execute = AsyncMock(return_value=json.dumps({"weak_areas": []}))

        service = ChatService(repo=None, llm=fake_llm, memory_service=None, memory_extractor=None)
        answer, tokens = await service._generate_with_tools(
            messages=[{"role": "user", "content": "loop forever"}], user_id="u1",
        )

    # بعد از MAX_TOOL_ITERATIONS دور (۳ تا)، باید بره سراغ generate() عادی
    assert answer == "fallback answer"
    assert tokens == 30 + 5