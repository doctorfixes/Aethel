"""Tests for app.py — FastAPI endpoints and request validation."""

from unittest.mock import MagicMock, patch

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


def test_system_prompt_includes_claude_md_content(tmp_path, monkeypatch):
    md = tmp_path / "context.md"
    md.write_text("Custom pedagogical context here")
    monkeypatch.setattr("app.CLAUDE_MD", md)
    prompt = _build_system_prompt("topic", 10)
    assert "Custom pedagogical context here" in prompt


# --- GET /health ---

@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    async with test_client as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- GET / ---

@pytest.mark.asyncio
async def test_index_returns_html(tmp_path, monkeypatch, test_client):
    html_file = tmp_path / "index.html"
    html_file.write_text("<h1>Test</h1>")
    monkeypatch.chdir(tmp_path)
    async with test_client as client:
        resp = await client.get("/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_index_fallback_when_missing(tmp_path, monkeypatch, test_client):
    monkeypatch.chdir(tmp_path)
    async with test_client as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "Æthel" in resp.text


# --- GET /privacy ---

@pytest.mark.asyncio
async def test_privacy_returns_html(tmp_path, monkeypatch, test_client):
    html_file = tmp_path / "privacy.html"
    html_file.write_text("<h1>Privacy</h1>")
    monkeypatch.chdir(tmp_path)
    async with test_client as client:
        resp = await client.get("/privacy")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_privacy_fallback_when_missing(tmp_path, monkeypatch, test_client):
    monkeypatch.chdir(tmp_path)
    async with test_client as client:
        resp = await client.get("/privacy")
    assert resp.status_code == 200
    assert "Privacy" in resp.text


# --- POST /generate-lesson: input validation ---

@pytest.mark.asyncio
async def test_generate_lesson_empty_topic_400(test_client):
    async with test_client as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "", "age": 10, "student_id": "test"},
        )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_lesson_whitespace_topic_400(test_client):
    async with test_client as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "   ", "age": 10, "student_id": "test"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_generate_lesson_age_too_low_400(test_client):
    async with test_client as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "gravity", "age": 2, "student_id": "test"},
        )
    assert resp.status_code == 400
    assert "age" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_lesson_age_too_high_400(test_client):
    async with test_client as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "gravity", "age": 25, "student_id": "test"},
        )
    assert resp.status_code == 400
    assert "age" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_lesson_missing_topic_422(test_client):
    """Pydantic rejects the request before our handler runs."""
    async with test_client as client:
        resp = await client.post(
            "/generate-lesson",
            json={"age": 10},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_lesson_missing_age_422(test_client):
    async with test_client as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "gravity"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_lesson_string_age_422(test_client):
    async with test_client as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "gravity", "age": "ten"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_lesson_negative_age_400(test_client):
    async with test_client as client:
        resp = await client.post(
            "/generate-lesson",
            json={"topic": "gravity", "age": -1},
        )
    assert resp.status_code == 400


# --- POST /generate-lesson: boundary ages ---

def _mock_orchestrator(lesson_text="A lesson about gravity."):
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = lesson_text
    mock_message = MagicMock()
    mock_message.content = [mock_block]
    mock_runner = MagicMock()
    mock_runner.get_final_message.return_value = mock_message
    return mock_runner


@pytest.mark.asyncio
async def test_generate_lesson_boundary_age_4_accepted(test_client):
    with patch("app.anthropic.Anthropic") as MockClient:
        MockClient.return_value.beta.messages.tool_runner.return_value = (
            _mock_orchestrator()
        )
        async with test_client as client:
            resp = await client.post(
                "/generate-lesson",
                json={"topic": "gravity", "age": 4, "student_id": "test"},
            )
    assert resp.status_code == 200
    assert resp.json()["lesson"] == "A lesson about gravity."


@pytest.mark.asyncio
async def test_generate_lesson_boundary_age_18_accepted(test_client):
    with patch("app.anthropic.Anthropic") as MockClient:
        MockClient.return_value.beta.messages.tool_runner.return_value = (
            _mock_orchestrator("Advanced lesson on quantum mechanics.")
        )
        async with test_client as client:
            resp = await client.post(
                "/generate-lesson",
                json={"topic": "quantum mechanics", "age": 18},
            )
    assert resp.status_code == 200
    assert "quantum" in resp.json()["lesson"].lower()


@pytest.mark.asyncio
async def test_generate_lesson_default_student_id(test_client):
    with patch("app.anthropic.Anthropic") as MockClient:
        MockClient.return_value.beta.messages.tool_runner.return_value = (
            _mock_orchestrator("Lesson content.")
        )
        async with test_client as client:
            resp = await client.post(
                "/generate-lesson",
                json={"topic": "gravity", "age": 10},
            )
    assert resp.status_code == 200
    assert resp.json()["student_id"] == "anonymous"


@pytest.mark.asyncio
async def test_generate_lesson_response_shape(test_client):
    """Verify the response contains all expected fields."""
    with patch("app.anthropic.Anthropic") as MockClient:
        MockClient.return_value.beta.messages.tool_runner.return_value = (
            _mock_orchestrator("Full lesson here.")
        )
        async with test_client as client:
            resp = await client.post(
                "/generate-lesson",
                json={"topic": "gravity", "age": 10, "student_id": "s1"},
            )
    body = resp.json()
    assert set(body.keys()) == {"lesson", "student_id", "topic"}
    assert body["topic"] == "gravity"
    assert body["student_id"] == "s1"


@pytest.mark.asyncio
async def test_generate_lesson_strips_whitespace(test_client):
    """The orchestrator output is .strip()ed."""
    with patch("app.anthropic.Anthropic") as MockClient:
        MockClient.return_value.beta.messages.tool_runner.return_value = (
            _mock_orchestrator("\n\n  Lesson with whitespace.  \n\n")
        )
        async with test_client as client:
            resp = await client.post(
                "/generate-lesson",
                json={"topic": "gravity", "age": 10},
            )
    assert resp.json()["lesson"] == "Lesson with whitespace."


@pytest.mark.asyncio
async def test_generate_lesson_anthropic_error_propagates():
    """If the Anthropic client raises, the error propagates through the endpoint."""
    with patch("app.anthropic.Anthropic") as MockClient:
        mock_runner = MagicMock()
        mock_runner.get_final_message.side_effect = RuntimeError("API key invalid")
        MockClient.return_value.beta.messages.tool_runner.return_value = mock_runner
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/generate-lesson",
                json={"topic": "gravity", "age": 10},
            )
    assert resp.status_code == 500
