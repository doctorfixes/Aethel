"""Shared test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from app import app


@pytest.fixture
def test_client():
    """Yield an async httpx client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def isolated_profiles(tmp_path, monkeypatch):
    """Redirect memory file I/O to a temp directory."""
    fake_profiles = tmp_path / "student_profile.json"
    fake_audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr("agents.memory.PROFILES_PATH", fake_profiles)
    monkeypatch.setattr("agents.memory.AUDIT_PATH", fake_audit)
    return fake_profiles, fake_audit
