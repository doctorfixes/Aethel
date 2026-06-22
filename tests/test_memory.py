"""Tests for agents/memory.py — student profile persistence."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.memory import (
    AUDIT_PATH,
    PROFILES_PATH,
    _append_audit,
    _read_profile,
    _write_profile,
    read_memory,
    write_memory,
)


@pytest.fixture(autouse=True)
def _isolate_files(tmp_path, monkeypatch):
    """Redirect all file I/O to a temp directory so tests don't clash."""
    fake_profiles = tmp_path / "student_profile.json"
    fake_audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr("agents.memory.PROFILES_PATH", fake_profiles)
    monkeypatch.setattr("agents.memory.AUDIT_PATH", fake_audit)
    return fake_profiles, fake_audit


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


def test_write_memory_duplicate_topic_not_added_twice():
    write_memory("alice", "gravity", True)
    write_memory("alice", "gravity", True)
    profile = _read_profile("alice")
    assert profile["mastered_topics"].count("gravity") == 1


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
