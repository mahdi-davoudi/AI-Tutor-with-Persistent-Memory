from app.domain.skill_tracker import SkillTracker


def make_memory(topic, memory_type, key="", value="", importance=0.5, frequency=1):
    return {
        "topic": topic,
        "memory_type": memory_type,
        "key": key,
        "value": value,
        "importance": importance,
        "frequency": frequency,
    }


# ---------------------------------------------------------------------------
# Bug fix: weak_area / strong_area must extract subtopic from `value`, not `key`
# ---------------------------------------------------------------------------

def test_weak_area_extracts_subtopic_from_value_not_key():
    # key deliberately points at an unrelated subtopic to prove `value` wins
    mem = make_memory(
        topic="python",
        memory_type="weak_area",
        key="some_unrelated_key",
        value="Closures",
        importance=0.8,
    )

    result = SkillTracker.build([mem])

    assert "closures" in result["python"]
    assert "some_unrelated_key" not in result["python"]
    entry = result["python"]["closures"]
    assert entry.tag == "weak"
    assert entry.importance == 0.8


def test_strong_area_extracts_subtopic_from_value_with_spaces_converted():
    mem = make_memory(
        topic="python",
        memory_type="strong_area",
        key="irrelevant",
        value="Object Oriented Programming",
    )

    result = SkillTracker.build([mem])

    assert "object_oriented_programming" in result["python"]
    assert result["python"]["object_oriented_programming"].tag == "strong"


def test_weak_area_falls_back_to_key_derivation_when_value_missing():
    # if value is empty, weak_area/strong_area falls through to the key-based path
    mem = make_memory(
        topic="python",
        memory_type="weak_area",
        key="python_recursion_skill",
        value="",
    )

    result = SkillTracker.build([mem])

    assert "recursion" in result["python"]
    assert result["python"]["recursion"].tag == "weak"


# ---------------------------------------------------------------------------
# Bug fix: skill_level memories are always neutral, never weak/strong
# ---------------------------------------------------------------------------

def test_skill_level_always_neutral_even_with_strong_language():
    mem = make_memory(
        topic="python",
        memory_type="skill_level",
        key="python_level",
        value="advanced",  # would resolve to "strong" if tag weren't forced neutral
    )

    result = SkillTracker.build([mem])

    entry = result["python"]["skill_level"]
    assert entry.tag == "neutral"


def test_skill_level_always_neutral_even_with_weak_language():
    mem = make_memory(
        topic="python",
        memory_type="skill_level",
        key="python_level",
        value="just started, still a beginner",
    )

    result = SkillTracker.build([mem])

    entry = result["python"]["skill_level"]
    assert entry.tag == "neutral"


def test_regression_python_level_skill_level_never_produces_weak_or_strong_entry():
    """Exact real-world data that originally exposed the bug: key='python_level',
    memory_type='skill_level'. This must never produce a weak/strong-tagged
    entry literally named 'skill_level' (or anything else)."""
    mem = make_memory(
        topic="python",
        memory_type="skill_level",
        key="python_level",
        value="beginner",
    )

    result = SkillTracker.build([mem])

    for entry in result["python"].values():
        assert entry.tag == "neutral"
    assert result["python"]["skill_level"].tag == "neutral"
    assert result["python"]["skill_level"].level_hint == "beginner"


# ---------------------------------------------------------------------------
# level_hint parsing from skill_level values
# ---------------------------------------------------------------------------

def test_level_hint_parses_beginner_alias():
    mem = make_memory(topic="python", memory_type="skill_level", key="python_level", value="novice")
    result = SkillTracker.build([mem])
    assert result["python"]["skill_level"].level_hint == "beginner"


def test_level_hint_parses_intermediate_alias():
    mem = make_memory(topic="python", memory_type="skill_level", key="python_level", value="medium")
    result = SkillTracker.build([mem])
    assert result["python"]["skill_level"].level_hint == "intermediate"


def test_level_hint_parses_advanced_alias():
    mem = make_memory(topic="python", memory_type="skill_level", key="python_level", value="expert")
    result = SkillTracker.build([mem])
    assert result["python"]["skill_level"].level_hint == "advanced"


def test_level_hint_is_none_when_value_has_no_known_alias():
    mem = make_memory(topic="python", memory_type="skill_level", key="python_level", value="pretty good honestly")
    result = SkillTracker.build([mem])
    assert result["python"]["skill_level"].level_hint is None


def test_level_hint_is_none_for_non_skill_level_memory_types():
    mem = make_memory(topic="python", memory_type="weak_area", value="advanced topics")
    result = SkillTracker.build([mem])
    entry = next(iter(result["python"].values()))
    assert entry.level_hint is None


# ---------------------------------------------------------------------------
# General / non weak-strong-skill_level subtopic derivation from key
# ---------------------------------------------------------------------------

def test_general_memory_type_derives_subtopic_from_key_with_suffix_stripped():
    mem = make_memory(
        topic="python",
        memory_type="general",
        key="python_decorators_skill",
        value="I struggle with decorators",
    )

    result = SkillTracker.build([mem])

    assert "decorators" in result["python"]
    assert result["python"]["decorators"].tag == "weak"


def test_invalid_subtopic_falls_back_to_memory_type():
    # key reduces to "level" after stripping the topic prefix, which is an
    # invalid/reserved subtopic name, so it falls back to memory_type
    mem = make_memory(
        topic="python",
        memory_type="learning_topic",
        key="python_level",
        value="comfortable",
    )

    result = SkillTracker.build([mem])

    assert "learning_topic" in result["python"]
    assert "level" not in result["python"]


# ---------------------------------------------------------------------------
# Topic filtering
# ---------------------------------------------------------------------------

def test_general_or_empty_topic_is_skipped():
    memories = [
        make_memory(topic="general", memory_type="weak_area", value="x"),
        make_memory(topic="", memory_type="weak_area", value="y"),
    ]

    result = SkillTracker.build(memories)

    assert result == {}


# ---------------------------------------------------------------------------
# Merging behavior for repeated subtopics
# ---------------------------------------------------------------------------

def test_merging_existing_entry_keeps_max_importance_sums_frequency_and_does_not_downgrade_tag():
    memories = [
        make_memory(topic="python", memory_type="weak_area", value="closures", importance=0.5, frequency=1),
        make_memory(
            topic="python",
            memory_type="skill_level",
            key="python_closures_level",
            value="intermediate",
            importance=0.9,
            frequency=2,
        ),
    ]

    result = SkillTracker.build(memories)

    entry = result["python"]["closures"]
    # tag stays "weak" even though the second (neutral) memory merged in
    assert entry.tag == "weak"
    assert entry.importance == 0.9
    assert entry.frequency == 3
    assert entry.level_hint == "intermediate"