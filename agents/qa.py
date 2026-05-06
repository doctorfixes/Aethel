from anthropic import beta_tool


_UNSAFE_TERMS = [
    "violence", "gore", "suicide", "self-harm", "explicit", "sexual",
    "drug", "alcohol", "weapon", "kill", "murder",
]

_REQUIRED_SOURCE_MARKERS = ["[Source:", "wikipedia.org", "http"]


@beta_tool
def validate_lesson(lesson: str, age: int) -> str:
    """Check that a generated lesson meets quality and safety standards before delivery.

    Args:
        lesson: The full lesson text to validate
        age: The target student age in years
    """
    issues: list[str] = []

    if len(lesson.strip()) < 150:
        issues.append("Lesson is too short (< 150 characters) — expand the explanation.")

    has_source = any(marker in lesson for marker in _REQUIRED_SOURCE_MARKERS)
    if not has_source:
        issues.append("No source citation found — add a [Source: ...] reference.")

    lesson_lower = lesson.lower()
    flagged = [t for t in _UNSAFE_TERMS if t in lesson_lower]
    if flagged:
        issues.append(f"Unsafe content detected: {', '.join(flagged)}. Remove or rephrase.")

    if age <= 8 and len(lesson) > 1200:
        issues.append(
            f"Lesson is too long ({len(lesson)} chars) for age {age} — keep under 1200 characters."
        )

    has_question = "?" in lesson
    if not has_question:
        issues.append("No closing question found — add a reflective question for the student.")

    if issues:
        return "FAIL\n" + "\n".join(f"- {issue}" for issue in issues)

    return f"PASS — lesson meets quality and safety standards for age {age}."
