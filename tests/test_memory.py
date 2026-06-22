"""Tests for agents/memory.py — student profile persistence."""

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from agents.memory import (
    _read_profile,
    _write_profile,
    read_memory,
    write_memory,
)


@pytest.fixture(autouse=True)
def _isolate_files(isolated_profiles):
    """Use the shared fixture from conftest to redirect file I/O."""


# --- _read_profile / _write_profile ---

def test_read_profile_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.memory.PROFILES_PATH", tmp_path / "missing.json")
    assert _read_profile("alice") == {}


def test_write_then_read_profile(tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    monkeypatch.setattr("agents.memory.PROFILES_PATH", path)
    profile = {"level": 2, "mastered_topics": ["gravity"], "gap_areas": []}
    _write_profile("alice", profile)
    assert _read_profile("alice") == profile


def test_write_preserves_other_students(tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    monkeypatch.setattr("agents.memory.PROFILES_PATH", path)
    _write_profile("alice", {"level": 1, "mastered_topics": [], "gap_areas": []})
    _write_profile("bob", {"level": 3, "mastered_topics": ["math"], "gap_areas": []})
    assert _read_profile("alice")["level"] == 1
    assert _read_profile("bob")["level"] == 3


def test_corrupted_json_returns_empty(tmp_path, monkeypatch):
    """Corrupted profile file should not crash — return empty profile."""
    path = tmp_path / "profiles.json"
    path.write_text("{this is not valid json!!!")
    monkeypatch.setattr("agents.memory.PROFILES_PATH", path)
    assert _read_profile("alice") == {}


def test_empty_file_returns_empty(tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    path.write_text("")
    monkeypatch.setattr("agents.memory.PROFILES_PATH", path)
    assert _read_profile("alice") == {}


# --- read_memory (tool) ---

def test_read_memory_new_student():
    result = read_memory("unknown_student")
    assert "No profile found" in result
    assert "unknown_student" in result


def test_read_memory_existing_student(tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    monkeypatch.setattr("agents.memory.PROFILES_PATH", path)
    profile = {
        "level": 2,
        "mastered_topics": ["gravity", "photosynthesis"],
        "gap_areas": [{"topic": "fractions", "note": "Struggled with denominators"}],
    }
    _write_profile("alice", profile)
    result = read_memory("alice")
    assert "Level: 2" in result
    assert "gravity" in result
    assert "fractions" in result
    assert "Struggled with denominators" in result


def test_read_memory_no_gaps_shows_none():
    _write_profile("alice", {"level": 1, "mastered_topics": [], "gap_areas": []})
    result = read_memory("alice")
    assert "None recorded" in result


# --- write_memory (tool) ---

def test_write_memory_new_student_mastered():
    result = write_memory("newbie", "gravity", True)
    assert "mastered=True" in result
    assert "level=1" in result


def test_write_memory_increments_level():
    write_memory("alice", "gravity", True)
    write_memory("alice", "photosynthesis", True)
    result = write_memory("alice", "fractions", True)
    assert "level=2" in result


def test_write_memory_level_caps_at_5():
    for i in range(20):
        write_memory("alice", f"topic_{i}", True)
    result = write_memory("alice", "topic_final", True)
    assert "level=5" in result


def test_write_memory_level_boundary_values():
    """Level = min(5, len(mastered) // 3 + 1). Verify exact transitions."""
    for i in range(3):
        write_memory("alice", f"t{i}", True)
    profile = _read_profile("alice")
    assert profile["level"] == 2  # 3 topics → 3//3+1 = 2

    for i in range(3, 6):
        write_memory("alice", f"t{i}", True)
    profile = _read_profile("alice")
    assert profile["level"] == 3  # 6 topics → 6//3+1 = 3


def test_write_memory_duplicate_topic_not_added_twice():
    write_memory("alice", "gravity", True)
    write_memory("alice", "gravity", True)
    profile = _read_profile("alice")
    assert profile["mastered_topics"].count("gravity") == 1


def test_write_memory_not_mastered_does_not_add_topic():
    write_memory("alice", "gravity", False)
    profile = _read_profile("alice")
    assert "gravity" not in profile.get("mastered_topics", [])


def test_write_memory_gap_note_added():
    write_memory("alice", "fractions", False, gap_note="Confused by mixed numbers")
    profile = _read_profile("alice")
    gaps = profile["gap_areas"]
    assert len(gaps) == 1
    assert gaps[0]["topic"] == "fractions"
    assert "mixed numbers" in gaps[0]["note"]


def test_write_memory_gap_note_updated():
    write_memory("alice", "fractions", False, gap_note="First attempt")
    write_memory("alice", "fractions", False, gap_note="Still struggling")
    profile = _read_profile("alice")
    gaps = [g for g in profile["gap_areas"] if g["topic"] == "fractions"]
    assert len(gaps) == 1
    assert gaps[0]["note"] == "Still struggling"


def test_write_memory_empty_gap_note_not_recorded():
    write_memory("alice", "gravity", True, gap_note="")
    profile = _read_profile("alice")
    assert profile["gap_areas"] == []


def test_write_memory_mastered_and_gap_together():
    """A topic can be mastered yet still have a gap note."""
    write_memory("alice", "gravity", True, gap_note="Weak on units")
    profile = _read_profile("alice")
    assert "gravity" in profile["mastered_topics"]
    assert any(g["topic"] == "gravity" for g in profile["gap_areas"])


# --- Audit log ---

def test_audit_log_appended(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("agents.memory.AUDIT_PATH", audit_path)
    write_memory("alice", "gravity", True)
    write_memory("alice", "photosynthesis", False, gap_note="Needs review")

    lines = audit_path.read_text().strip().split("\n")
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["student_id"] == "alice"
    assert first["topic"] == "gravity"
    assert first["mastered"] is True
    assert "ts" in first

    second = json.loads(lines[1])
    assert second["mastered"] is False
    assert second["gap_note"] == "Needs review"


def test_audit_timestamp_is_utc_iso(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("agents.memory.AUDIT_PATH", audit_path)
    write_memory("alice", "gravity", True)
    record = json.loads(audit_path.read_text().strip())
    assert "+" in record["ts"] or record["ts"].endswith("Z") or "UTC" in record["ts"]


def test_audit_includes_level_after(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("agents.memory.AUDIT_PATH", audit_path)
    write_memory("alice", "gravity", True)
    record = json.loads(audit_path.read_text().strip())
    assert "level_after" in record
    assert record["level_after"] == 1


# --- Concurrency ---

def test_concurrent_writes_lose_data_without_locking(tmp_path, monkeypatch):
    """Document that concurrent writes lose data without file locking.

    This writes 10 topics in parallel threads. Without locking, race
    conditions mean the final profile will likely have fewer than 10
    topics. We verify the file isn't corrupted (valid JSON, non-empty)
    and that data was lost — proving locking is needed.
    """
    path = tmp_path / "profiles.json"
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("agents.memory.PROFILES_PATH", path)
    monkeypatch.setattr("agents.memory.AUDIT_PATH", audit_path)

    def write_topic(i):
        write_memory("alice", f"concurrent_topic_{i}", True)

    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(write_topic, range(10)))

    profile = _read_profile("alice")
    assert profile != {}
    mastered = profile.get("mastered_topics", [])
    assert len(mastered) < 10
