import pytest
from app.domain.skill_tracker import SkillTracker, SkillEntry
from app.domain.mastery_estimator import MasteryEstimator
from app.services.profile_service import ProfileService

# Fixtures
# ─────────────────────────────────────────────

def mem(topic, key, memory_type, value, importance=0.7, frequency=1):
    return {
        "topic": topic,
        "key": key,
        "memory_type": memory_type,
        "value": value,
        "importance": importance,
        "frequency": frequency,
    }

# SkillTracker
# ─────────────────────────────────────────────

class TestSkillTracker:

    def test_groups_by_topic(self):
        memories = [
            mem("python", "python_loops", "weak_area", "struggles with loops"),
            mem("mongodb", "mongodb_aggregation", "weak_area", "struggles with aggregation"),
        ]
        skill_map = SkillTracker.build(memories)
        assert "python" in skill_map
        assert "mongodb" in skill_map

    def test_weak_area_tag(self):
        memories = [mem("python", "python_recursion", "weak_area", "struggles with recursion")]
        skill_map = SkillTracker.build(memories)
        assert skill_map["python"]["recursion"].tag == "weak"

    def test_strong_area_tag(self):
        memories = [mem("python", "python_functions", "strong_area", "comfortable with functions")]
        skill_map = SkillTracker.build(memories)
        assert skill_map["python"]["functions"].tag == "strong"

    def test_skill_level_beginner_is_weak(self):
        memories = [mem("python", "python_loops_skill", "skill_level", "user is beginner in loops")]
        skill_map = SkillTracker.build(memories)
        assert skill_map["python"]["loops"].tag == "weak"

    def test_skill_level_advanced_is_strong(self):
        memories = [mem("arduino", "arduino_interrupts_skill", "skill_level", "user is advanced in arduino")]
        skill_map = SkillTracker.build(memories)
        assert skill_map["arduino"]["interrupts"].tag == "strong"

    def test_skill_level_intermediate_is_neutral(self):
        memories = [mem("math", "math_probability_skill", "skill_level", "user is intermediate in probability")]
        skill_map = SkillTracker.build(memories)
        assert skill_map["math"]["probability"].tag == "neutral"

    def test_skill_level_familiar_is_strong(self):
        memories = [mem("arduino", "arduino_interrupts_skill", "skill_level", "user is familiar with interrupts")]
        skill_map = SkillTracker.build(memories)
        assert skill_map["arduino"]["interrupts"].tag == "strong"

    def test_frequency_accumulates(self):
        memories = [
            mem("python", "python_loops", "weak_area", "struggles", frequency=2),
            mem("python", "python_loops", "weak_area", "struggles again", frequency=3),
        ]
        skill_map = SkillTracker.build(memories)
        assert skill_map["python"]["loops"].frequency == 5

    def test_importance_keeps_max(self):
        memories = [
            mem("python", "python_loops", "weak_area", "...", importance=0.4),
            mem("python", "python_loops", "weak_area", "...", importance=0.9),
        ]
        skill_map = SkillTracker.build(memories)
        assert skill_map["python"]["loops"].importance == pytest.approx(0.9)

    def test_general_topic_skipped(self):
        memories = [mem("general", "general_tip", "learning_topic", "...")]
        skill_map = SkillTracker.build(memories)
        assert skill_map == {}

    def test_invalid_subtopic_falls_back(self):

        memories = [mem("mblock", "mblock_beginner_level", "skill_level", "user is beginner")]
        skill_map = SkillTracker.build(memories)

        assert "mblock" in skill_map
        subtopics = list(skill_map["mblock"].keys())
        assert "beginner" not in subtopics  

# MasteryEstimator
# ─────────────────────────────────────────────

def make_skill_map(entries):
    skill_map = {}
    for e in entries:
        skill_map.setdefault(e["topic"], {})[e["subtopic"]] = SkillEntry(
            subtopic=e["subtopic"],
            tag=e["tag"],
            importance=e.get("importance", 0.7),
            frequency=e.get("frequency", 1),
            level_hint=e.get("level_hint"),
        )
    return skill_map


class TestMasteryEstimator:

    def test_all_strong_gives_1(self):
        sm = make_skill_map([
            {"topic": "python", "subtopic": "loops",     "tag": "strong"},
            {"topic": "python", "subtopic": "functions", "tag": "strong"},
        ])
        result = MasteryEstimator.estimate(sm)
        assert result["python"].mastery == pytest.approx(1.0)
        assert result["python"].level == "advanced"

    def test_all_weak_gives_0(self):
        sm = make_skill_map([
            {"topic": "python", "subtopic": "recursion",  "tag": "weak"},
            {"topic": "python", "subtopic": "decorators", "tag": "weak"},
        ])
        result = MasteryEstimator.estimate(sm)
        assert result["python"].mastery == pytest.approx(0.0)
        assert result["python"].level == "beginner"

    def test_all_neutral_intermediate_hint(self):
        sm = make_skill_map([
            {"topic": "math", "subtopic": "probability", "tag": "neutral", "level_hint": "intermediate"},
        ])
        result = MasteryEstimator.estimate(sm)
        assert result["math"].mastery == pytest.approx(0.45)
        assert result["math"].level == "intermediate"

    def test_all_neutral_advanced_hint(self):
        sm = make_skill_map([
            {"topic": "math", "subtopic": "calculus", "tag": "neutral", "level_hint": "advanced"},
        ])
        result = MasteryEstimator.estimate(sm)
        assert result["math"].mastery == pytest.approx(0.75)
        assert result["math"].level == "advanced"

    def test_all_neutral_no_hint_gives_beginner(self):
        sm = make_skill_map([
            {"topic": "math", "subtopic": "calculus", "tag": "neutral"},
        ])
        result = MasteryEstimator.estimate(sm)
        assert result["math"].mastery == pytest.approx(0.15)
        assert result["math"].level == "beginner"

    def test_strong_and_weak_lists(self):
        sm = make_skill_map([
            {"topic": "python", "subtopic": "functions", "tag": "strong"},
            {"topic": "python", "subtopic": "recursion", "tag": "weak"},
        ])
        result = MasteryEstimator.estimate(sm)
        assert "functions" in result["python"].strong
        assert "recursion" in result["python"].weak

    def test_mastery_clamped(self):
        sm = make_skill_map([
            {"topic": "x", "subtopic": "a", "tag": "strong", "importance": 1.0, "frequency": 999},
        ])
        result = MasteryEstimator.estimate(sm)
        assert 0.0 <= result["x"].mastery <= 1.0

    def test_empty_map(self):
        assert MasteryEstimator.estimate({}) == {}


class TestDetectStyle:

    def test_example_based(self):
        raw = [
            {"value": "user asked for example"},
            {"value": "user wants code sample"},
            {"value": "user said show me"},
        ]
        assert ProfileService._detect_style(raw) == "example-based"

    def test_no_signal_returns_none(self):
        raw = [{"value": "user is beginner"}, {"value": "user knows loops"}]
        assert ProfileService._detect_style(raw) is None

    def test_ambiguous_returns_none(self):
        raw = [
            {"value": "example"},
            {"value": "explain why"},
            {"value": "practice exercise"},
        ]
        
        assert ProfileService._detect_style(raw) is None