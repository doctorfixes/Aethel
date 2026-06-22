"""Tests for agents/qa.py — lesson validation logic."""

import pytest

from agents.qa import validate_lesson


def _make_lesson(length=200, source=True, question=True, extra=""):
    """Build a synthetic lesson string with controllable properties."""
    body = "A " * (length // 2)
    if source:
        body += "[Source: https://en.wikipedia.org/wiki/Test] "
    if question:
        body += "What did you learn?"
    body += extra
    return body


# --- Length validation ---

def test_too_short_lesson_fails():
    result = validate_lesson("Short.", 10)
    assert "FAIL" in result
    assert "too short" in result


def test_minimum_length_passes():
    lesson = _make_lesson(length=200)
    result = validate_lesson(lesson, 12)
    assert "PASS" in result


# --- Source citation validation ---

def test_missing_source_fails():
    lesson = _make_lesson(source=False)
    result = validate_lesson(lesson, 12)
    assert "FAIL" in result
    assert "No source citation" in result


def test_source_with_bracket_format_passes():
    lesson = _make_lesson(source=True)
    result = validate_lesson(lesson, 12)
    assert "PASS" in result


def test_source_with_bare_url_passes():
    lesson = "A " * 100 + "https://en.wikipedia.org/wiki/Test What did you learn?"
    result = validate_lesson(lesson, 12)
    assert "PASS" in result


# --- Unsafe content detection ---

def test_unsafe_term_violence_fails():
    lesson = _make_lesson(extra=" violence is bad")
    result = validate_lesson(lesson, 10)
    assert "FAIL" in result
    assert "violence" in result


def test_unsafe_term_case_insensitive():
    lesson = _make_lesson(extra=" VIOLENCE in uppercase")
    result = validate_lesson(lesson, 10)
    assert "FAIL" in result
    assert "violence" in result


def test_multiple_unsafe_terms_listed():
    lesson = _make_lesson(extra=" violence and gore here")
    result = validate_lesson(lesson, 10)
    assert "FAIL" in result
    assert "violence" in result
    assert "gore" in result


def test_safe_lesson_passes():
    lesson = _make_lesson()
    result = validate_lesson(lesson, 10)
    assert "PASS" in result


def test_substring_no_false_positive_drugstore():
    """'drugstore' should NOT trigger the 'drug' filter (word-boundary match)."""
    lesson = _make_lesson(extra=" I visited the drugstore today")
    result = validate_lesson(lesson, 10)
    assert "PASS" in result


def test_substring_no_false_positive_killer():
    """'killer whale' should NOT trigger the 'kill' filter."""
    lesson = _make_lesson(extra=" The killer whale is a marine mammal")
    result = validate_lesson(lesson, 10)
    assert "PASS" in result


def test_substring_no_false_positive_alcoholic():
    """'non-alcoholic' should NOT trigger the 'alcohol' filter."""
    lesson = _make_lesson(extra=" They served non-alcoholic beverages")
    result = validate_lesson(lesson, 10)
    assert "PASS" in result


def test_standalone_unsafe_term_still_caught():
    """The actual word 'drug' on its own must still be caught."""
    lesson = _make_lesson(extra=" the drug was discovered in 1920")
    result = validate_lesson(lesson, 10)
    assert "FAIL" in result
    assert "drug" in result


def test_hyphenated_unsafe_term_self_harm():
    """'self-harm' should still be caught as a complete term."""
    lesson = _make_lesson(extra=" self-harm is dangerous")
    result = validate_lesson(lesson, 10)
    assert "FAIL" in result
    assert "self-harm" in result


@pytest.mark.parametrize("term", [
    "violence", "gore", "suicide", "self-harm", "explicit",
    "sexual", "drug", "alcohol", "weapon", "kill", "murder",
])
def test_each_unsafe_term_detected(term):
    lesson = _make_lesson(extra=f" the topic of {term} is serious")
    result = validate_lesson(lesson, 10)
    assert "FAIL" in result
    assert term in result


# --- Age-gated length ---

def test_young_learner_long_lesson_fails():
    lesson = _make_lesson(length=1400)
    result = validate_lesson(lesson, 7)
    assert "FAIL" in result
    assert "too long" in result


def test_young_learner_short_lesson_passes():
    lesson = _make_lesson(length=400)
    result = validate_lesson(lesson, 7)
    assert "PASS" in result


def test_older_learner_long_lesson_passes():
    lesson = _make_lesson(length=1400)
    result = validate_lesson(lesson, 14)
    assert "PASS" in result


def test_age_boundary_8_applies_length_cap():
    lesson = _make_lesson(length=1400)
    result = validate_lesson(lesson, 8)
    assert "FAIL" in result
    assert "too long" in result


def test_age_boundary_9_no_length_cap():
    lesson = _make_lesson(length=1400)
    result = validate_lesson(lesson, 9)
    assert "PASS" in result


# --- Closing question ---

def test_missing_question_fails():
    lesson = _make_lesson(question=False)
    result = validate_lesson(lesson, 12)
    assert "FAIL" in result
    assert "No closing question" in result


def test_lesson_with_question_passes():
    lesson = _make_lesson(question=True)
    result = validate_lesson(lesson, 12)
    assert "PASS" in result


# --- Multiple failures ---

def test_multiple_issues_reported():
    result = validate_lesson("bad", 7)
    assert "FAIL" in result
    assert "too short" in result
    assert "No source citation" in result
    assert "No closing question" in result


# --- Edge cases ---

def test_empty_lesson():
    result = validate_lesson("", 10)
    assert "FAIL" in result


def test_whitespace_only_lesson():
    result = validate_lesson("   \n\t  ", 10)
    assert "FAIL" in result
    assert "too short" in result


def test_pass_message_includes_age():
    lesson = _make_lesson()
    result = validate_lesson(lesson, 15)
    assert "PASS" in result
    assert "15" in result
