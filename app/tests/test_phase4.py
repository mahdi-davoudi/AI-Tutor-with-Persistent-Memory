"""
تست فاز ۴ — بدون DB، بدون HTTP
pytest tests/test_phase4.py -v
"""

import pytest
from app.domain.prompt_builder import PromptBuilder
from app.schemas.learning_profile import LearningProfileSummary, TopicProfileSchema


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_profile(topics: dict, style=None) -> LearningProfileSummary:
    return LearningProfileSummary(
        user_id="test_user",
        topics={
            name: TopicProfileSchema(
                mastery=t["mastery"],
                level=t["level"],
                strong=t.get("strong", []),
                weak=t.get("weak", []),
                total_skills=t.get("total_skills", 1),
            )
            for name, t in topics.items()
        },
        preferred_style=style,
    )


class FakeMemory:
    def __init__(self, key, value):
        self.key = key
        self.value = value


# ─────────────────────────────────────────────
# PromptBuilder
# ─────────────────────────────────────────────

class TestPromptBuilder:

    def test_returns_list_of_dicts(self):
        messages = PromptBuilder.build([], "hello")
        assert isinstance(messages, list)
        assert all(isinstance(m, dict) for m in messages)

    def test_first_message_is_system(self):
        messages = PromptBuilder.build([], "hello")
        assert messages[0]["role"] == "system"

    def test_last_message_is_user(self):
        messages = PromptBuilder.build([], "hello")
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "hello"

    def test_history_preserved(self):
        history = [
            {"role": "user",      "content": "what is a loop?"},
            {"role": "assistant", "content": "a loop repeats code"},
        ]
        messages = PromptBuilder.build(history, "give example")
        roles = [m["role"] for m in messages]
        assert roles == ["system", "user", "assistant", "user"]

    def test_profile_injected_into_system(self):
        profile = make_profile({
            "python": {"mastery": 0.8, "level": "advanced", "strong": ["functions"], "weak": []},
        })
        messages = PromptBuilder.build([], "hello", profile=profile)
        system = messages[0]["content"]
        assert "python" in system
        assert "advanced" in system

    def test_weak_areas_in_system(self):
        profile = make_profile({
            "python": {"mastery": 0.1, "level": "beginner", "strong": [], "weak": ["recursion"]},
        })
        messages = PromptBuilder.build([], "hello", profile=profile)
        system = messages[0]["content"]
        assert "recursion" in system

    def test_preferred_style_in_system(self):
        profile = make_profile(
            {"python": {"mastery": 0.5, "level": "intermediate"}},
            style="example-based",
        )
        messages = PromptBuilder.build([], "hello", profile=profile)
        system = messages[0]["content"]
        assert "example-based" in system

    def test_memories_injected(self):
        memories = [
            FakeMemory("python_loops", "user struggles with loops"),
            FakeMemory("python_functions", "user is comfortable with functions"),
        ]
        messages = PromptBuilder.build([], "hello", memories=memories)
        system = messages[0]["content"]
        assert "python_loops" in system
        assert "python_functions" in system

    def test_no_profile_no_crash(self):
        messages = PromptBuilder.build([], "hello", profile=None, memories=None)
        assert messages[0]["role"] == "system"
        assert messages[-1]["content"] == "hello"

    def test_empty_profile_no_profile_section(self):
        profile = make_profile({})  # بدون هیچ topic
        messages = PromptBuilder.build([], "hello", profile=profile)
        system = messages[0]["content"]
        assert "Learning Profile" not in system

    def test_multiple_topics_all_present(self):
        profile = make_profile({
            "python":  {"mastery": 0.8, "level": "advanced"},
            "mongodb": {"mastery": 0.2, "level": "beginner"},
        })
        messages = PromptBuilder.build([], "hello", profile=profile)
        system = messages[0]["content"]
        assert "python" in system
        assert "mongodb" in system

    def test_history_roles_filtered(self):
        # role های غیر user/assistant باید filter بشن
        history = [
            {"role": "system",    "content": "old system"},
            {"role": "user",      "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        messages = PromptBuilder.build(history, "new message")
        roles = [m["role"] for m in messages]
        assert roles.count("system") == 1  # فقط یه system داریم