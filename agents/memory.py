import json
from datetime import datetime, timezone
from pathlib import Path
from anthropic import beta_tool

PROFILES_PATH = Path("student_profile.json")
AUDIT_PATH = Path("audit.jsonl")


def _read_profile(student_id: str) -> dict:
    if PROFILES_PATH.exists():
        try:
            data = json.loads(PROFILES_PATH.read_text())
        except (json.JSONDecodeError, ValueError):
            return {}
        return data.get(student_id, {})
    return {}


def _write_profile(student_id: str, profile: dict) -> None:
    data: dict = {}
    if PROFILES_PATH.exists():
        try:
            data = json.loads(PROFILES_PATH.read_text())
        except (json.JSONDecodeError, ValueError):
            data = {}
    data[student_id] = profile
    PROFILES_PATH.write_text(json.dumps(data, indent=2))


def _append_audit(record: dict) -> None:
    with AUDIT_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")


@beta_tool
def read_memory(student_id: str) -> str:
    """Read a student's learning profile to personalise the lesson.

    Args:
        student_id: The unique identifier for the student
    """
    profile = _read_profile(student_id)
    if not profile:
        return (
            f"No profile found for student '{student_id}'. "
            "Treat them as a new learner at level 1 with no prior topics."
        )
    mastered = profile.get("mastered_topics", [])
    gaps = profile.get("gap_areas", [])
    level = profile.get("level", 1)
    gap_lines = (
        "\n".join(f"  - {g['topic']}: {g['note']}" for g in gaps) if gaps else "  None recorded"
    )
    return (
        f"Student '{student_id}' profile:\n"
        f"  Level: {level}\n"
        f"  Mastered topics: {', '.join(mastered) if mastered else 'none yet'}\n"
        f"  Known gaps:\n{gap_lines}"
    )


@beta_tool
def write_memory(student_id: str, topic: str, mastered: bool, gap_note: str = "") -> str:
    """Update a student's learning profile after a lesson and log the interaction.

    Args:
        student_id: The unique identifier for the student
        topic: The topic that was just taught
        mastered: Whether the student demonstrated mastery of the topic
        gap_note: Optional note describing a specific gap or misconception observed
    """
    profile = _read_profile(student_id)
    if not profile:
        profile = {"level": 1, "mastered_topics": [], "gap_areas": []}

    if mastered and topic not in profile.get("mastered_topics", []):
        profile.setdefault("mastered_topics", []).append(topic)
        profile["level"] = min(5, len(profile["mastered_topics"]) // 3 + 1)

    if gap_note:
        gaps = profile.setdefault("gap_areas", [])
        existing = next((g for g in gaps if g["topic"] == topic), None)
        if existing:
            existing["note"] = gap_note
        else:
            gaps.append({"topic": topic, "note": gap_note})

    _write_profile(student_id, profile)

    audit_record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "student_id": student_id,
        "topic": topic,
        "mastered": mastered,
        "gap_note": gap_note,
        "level_after": profile["level"],
    }
    _append_audit(audit_record)

    return (
        f"Profile updated for '{student_id}': "
        f"topic='{topic}', mastered={mastered}, level={profile['level']}."
    )
