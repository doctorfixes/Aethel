"""Tests for agents/qa.py — lesson validation logic."""

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


def test_substring_false_positive_drug():
    """'drug' inside 'drugstore' triggers the filter — documents current behavior."""
    lesson = _make_lesson(extra=" I visited the drugstore today")
    result = validate_lesson(lesson, 10)
    assert "FAIL" in result
    assert "drug" in result
