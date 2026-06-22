"""Tests for app.py — FastAPI endpoints and request validation."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app, _build_system_prompt


# --- _build_system_prompt ---

def test_system_prompt_includes_topic_and_age():
    prompt = _build_system_prompt("gravity", 12)
    assert "'gravity'" in prompt
    assert "12" in prompt


def test_system_prompt_without_claude_md(tmp_path, monkeypatch):
    monkeypatch.setattr("app.CLAUDE_MD", tmp_path / "nonexistent.md")
    prompt = _build_system_prompt("topic", 10)
    assert "Æthel" in prompt


# --- GET /health ---

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- GET / ---

@pytest.mark.asyncio
async def test_index_returns_html(tmp_path, monkeypatch):
    html_file = tmp_path / "index.html"
    html_file.write_text("<h1>Test</h1>")
    monkeypatch.chdir(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_index_fallback_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "Æthel" in resp.text


# --- GET /privacy ---

@pytest.mark.asyncio
async def test_privacy_returns_html(tmp_path, monkeypatch):
    html_file = tmp_path / "privacy.html"
    html_file.write_text("<h1>Privacy</h1>")
    monkeypatch.chdir(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/privacy")
    assert resp.status_code == 200


# --- POST /generate-lesson validation ---

@pytest.mark.asyncio
async def test_generate_lesson_empty_topic_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "", "age": 10, "student_id": "test"},
        )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_lesson_whitespace_topic_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "   ", "age": 10, "student_id": "test"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_generate_lesson_age_too_low_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "gravity", "age": 2, "student_id": "test"},
        )
    assert resp.status_code == 400
    assert "age" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_lesson_age_too_high_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "gravity", "age": 25, "student_id": "test"},
        )
    assert resp.status_code == 400
    assert "age" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_lesson_boundary_age_4_accepted():
    """Age 4 should pass validation (but we mock the orchestrator)."""
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "A lesson about gravity."
    mock_message = MagicMock()
    mock_message.content = [mock_block]
    mock_runner = MagicMock()
    mock_runner.get_final_message.return_value = mock_message

    with patch("app.anthropic.Anthropic") as MockClient:
        MockClient.return_value.beta.messages.tool_runner.return_value = mock_runner
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/generate-lesson",
                json={"topic": "gravity", "age": 4, "student_id": "test"},
            )
    assert resp.status_code == 200
    assert resp.json()["lesson"] == "A lesson about gravity."


@pytest.mark.asyncio
async def test_generate_lesson_default_student_id():
    """student_id should default to 'anonymous'."""
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "Lesson content."
    mock_message = MagicMock()
    mock_message.content = [mock_block]
    mock_runner = MagicMock()
    mock_runner.get_final_message.return_value = mock_message

    with patch("app.anthropic.Anthropic") as MockClient:
        MockClient.return_value.beta.messages.tool_runner.return_value = mock_runner
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/generate-lesson",
                json={"topic": "gravity", "age": 10},
            )
    assert resp.status_code == 200
    assert resp.json()["student_id"] == "anonymous"
