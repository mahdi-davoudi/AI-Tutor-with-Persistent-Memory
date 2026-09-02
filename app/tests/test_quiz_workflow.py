import pytest
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

from app.domain.quiz_generator import QuizGenerator
from app.services.quiz_service import QuizService
from app.core.exceptions import NotFoundError


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


def make_question(question="Q?", options=None, correct_index=0, explanation="Because."):
    return {
        "question": question,
        "options": options if options is not None else ["a", "b", "c", "d"],
        "correct_index": correct_index,
        "explanation": explanation,
    }


def make_profile_summary(topics: dict):
    return SimpleNamespace(topics=topics)


# ---------------------------------------------------------------------------
# QuizGenerator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_returns_validated_questions():
    fake_response = {
        "questions": [
            make_question("What is a list?", correct_index=1),
            make_question("What is a tuple?", correct_index=2),
        ]
    }
    llm = FakeLLM(structured_response=fake_response)
    generator = QuizGenerator(llm=llm)

    result = await generator.generate(topic="python", weak_skills=["lists"])

    assert len(result) == 2
    assert result[0]["question"] == "What is a list?"
    assert result[0]["correct_index"] == 1
    assert len(result[0]["options"]) == 4


@pytest.mark.asyncio
async def test_generate_filters_malformed_questions():
    fake_response = {
        "questions": [
            make_question("Valid one", correct_index=0),
            make_question("Wrong option count", options=["a", "b", "c"], correct_index=0),
            make_question("Invalid correct_index", correct_index=5),
            make_question("Invalid correct_index type", correct_index="1"),
            {"question": "", "options": ["a", "b", "c", "d"], "correct_index": 0, "explanation": "x"},
            {"question": "No explanation", "options": ["a", "b", "c", "d"], "correct_index": 0, "explanation": ""},
        ]
    }
    llm = FakeLLM(structured_response=fake_response)
    generator = QuizGenerator(llm=llm)

    result = await generator.generate(topic="python", weak_skills=["recursion"])

    assert len(result) == 1
    assert result[0]["question"] == "Valid one"


@pytest.mark.asyncio
async def test_generate_returns_empty_list_when_all_invalid():
    fake_response = {
        "questions": [
            make_question(options=["a", "b"], correct_index=0),
        ]
    }
    llm = FakeLLM(structured_response=fake_response)
    generator = QuizGenerator(llm=llm)

    result = await generator.generate(topic="python", weak_skills=[])

    assert result == []


@pytest.mark.asyncio
async def test_generate_empty_weak_skills_uses_default_text():
    fake_response = {"questions": [make_question()]}
    llm = FakeLLM(structured_response=fake_response)
    generator = QuizGenerator(llm=llm)

    await generator.generate(topic="python", weak_skills=[])

    user_message = llm.last_messages[1]["content"]
    assert "general fundamentals" in user_message
    assert llm.last_schema_name == "quiz_generation"


@pytest.mark.asyncio
async def test_generate_missing_questions_key_returns_empty_list():
    llm = FakeLLM(structured_response={})
    generator = QuizGenerator(llm=llm)

    result = await generator.generate(topic="python", weak_skills=["loops"])

    assert result == []


# ---------------------------------------------------------------------------
# QuizService
# ---------------------------------------------------------------------------

def make_fake_quiz(**kwargs):
    """Stand-in for a Beanie Document instance that doesn't need init_beanie()."""
    quiz = SimpleNamespace(**kwargs)
    quiz.insert = AsyncMock(return_value=None)
    return quiz


@pytest.mark.asyncio
async def test_generate_quiz_with_explicit_topic():
    fake_topic = SimpleNamespace(weak=["recursion"], mastery=0.4)
    fake_summary = make_profile_summary({"python": fake_topic})
    fake_questions = [make_question()]

    with patch("app.services.quiz_service.LLMService"), \
         patch("app.services.quiz_service.QuizGenerator") as MockGenerator, \
         patch("app.services.quiz_service.ProfileService") as MockProfileService, \
         patch("app.services.quiz_service.Quiz", side_effect=make_fake_quiz) as MockQuiz:

        MockProfileService.return_value.get_summary = AsyncMock(return_value=fake_summary)
        MockGenerator.return_value.generate = AsyncMock(return_value=fake_questions)

        service = QuizService()
        quiz = await service.generate_quiz(user_id="u1", topic="python")

    assert quiz.user_id == "u1"
    assert quiz.topic == "python"
    assert quiz.weak_skills == ["recursion"]
    assert len(quiz.questions) == 1
    quiz.insert.assert_awaited_once()
    MockQuiz.assert_called_once_with(
        user_id="u1", topic="python", weak_skills=["recursion"], questions=fake_questions
    )


@pytest.mark.asyncio
async def test_generate_quiz_auto_pick_weakest_topic():
    strong_topic = SimpleNamespace(weak=[], mastery=0.9)
    weak_topic_1 = SimpleNamespace(weak=["loops"], mastery=0.5)
    weak_topic_2 = SimpleNamespace(weak=["recursion", "closures"], mastery=0.2)
    fake_summary = make_profile_summary({
        "sql": strong_topic,
        "python_basics": weak_topic_1,
        "python_advanced": weak_topic_2,
    })
    fake_questions = [make_question()]

    with patch("app.services.quiz_service.LLMService"), \
         patch("app.services.quiz_service.QuizGenerator") as MockGenerator, \
         patch("app.services.quiz_service.ProfileService") as MockProfileService, \
         patch("app.services.quiz_service.Quiz", side_effect=make_fake_quiz):

        MockProfileService.return_value.get_summary = AsyncMock(return_value=fake_summary)
        MockGenerator.return_value.generate = AsyncMock(return_value=fake_questions)

        service = QuizService()
        quiz = await service.generate_quiz(user_id="u1", topic=None)

    # weakest mastery (0.2) belongs to python_advanced
    assert quiz.topic == "python_advanced"
    assert quiz.weak_skills == ["recursion", "closures"]
    quiz.insert.assert_awaited_once()


@pytest.mark.asyncio
async def test_pick_weakest_topic_no_weak_areas_raises_not_found():
    strong_topic = SimpleNamespace(weak=[], mastery=0.9)
    fake_summary = make_profile_summary({"sql": strong_topic})

    with patch("app.services.quiz_service.LLMService"), \
         patch("app.services.quiz_service.QuizGenerator"), \
         patch("app.services.quiz_service.ProfileService") as MockProfileService:

        MockProfileService.return_value.get_summary = AsyncMock(return_value=fake_summary)

        service = QuizService()

        with pytest.raises(NotFoundError):
            await service.generate_quiz(user_id="u1", topic=None)


@pytest.mark.asyncio
async def test_generate_quiz_raises_not_found_when_no_questions_generated():
    fake_topic = SimpleNamespace(weak=["recursion"], mastery=0.4)
    fake_summary = make_profile_summary({"python": fake_topic})

    with patch("app.services.quiz_service.LLMService"), \
         patch("app.services.quiz_service.QuizGenerator") as MockGenerator, \
         patch("app.services.quiz_service.ProfileService") as MockProfileService:

        MockProfileService.return_value.get_summary = AsyncMock(return_value=fake_summary)
        MockGenerator.return_value.generate = AsyncMock(return_value=[])

        service = QuizService()

        with pytest.raises(NotFoundError):
            await service.generate_quiz(user_id="u1", topic="python")