import pytest
from app.domain.recommendation_engine import RecommendationEngine


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