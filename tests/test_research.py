"""Tests for agents/research.py — Wikipedia API integration."""

import httpx
import respx

from agents.research import research_topic


WIKI_BASE = "https://en.wikipedia.org/api/rest_v1/page/summary"


@respx.mock
def test_successful_lookup():
    respx.get(f"{WIKI_BASE}/Photosynthesis").mock(
        return_value=httpx.Response(
            200,
            json={
                "extract": "Photosynthesis is a biological process.",
                "content_urls": {},
            },
        )
    )
    result = research_topic("Photosynthesis")
    assert "[Source: https://en.wikipedia.org/wiki/Photosynthesis]" in result
    assert "Photosynthesis is a biological process." in result


@respx.mock
def test_topic_with_spaces_uses_underscores():
    respx.get(f"{WIKI_BASE}/Water_cycle").mock(
        return_value=httpx.Response(
            200, json={"extract": "The water cycle describes..."}
        )
    )
    result = research_topic("Water cycle")
    assert "Water_cycle" in result


@respx.mock
def test_404_returns_fallback():
    respx.get(f"{WIKI_BASE}/Nonexistent_topic_xyz").mock(
        return_value=httpx.Response(404)
    )
    result = research_topic("Nonexistent topic xyz")
    assert "404" in result
    assert "general knowledge" in result


@respx.mock
def test_500_returns_fallback():
    respx.get(f"{WIKI_BASE}/Server_error").mock(
        return_value=httpx.Response(500)
    )
    result = research_topic("Server error")
    assert "500" in result
    assert "general knowledge" in result


@respx.mock
def test_empty_extract_returns_status_code():
    respx.get(f"{WIKI_BASE}/Empty_page").mock(
        return_value=httpx.Response(200, json={"extract": ""})
    )
    result = research_topic("Empty page")
    assert "200" in result


@respx.mock
def test_missing_extract_key():
    respx.get(f"{WIKI_BASE}/No_extract").mock(
        return_value=httpx.Response(200, json={"title": "No extract"})
    )
    result = research_topic("No extract")
    assert "200" in result


@respx.mock
def test_timeout_returns_fallback():
    respx.get(f"{WIKI_BASE}/Slow_topic").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    result = research_topic("Slow topic")
    assert "timed out" in result.lower()
    assert "general knowledge" in result


@respx.mock
def test_generic_exception_returns_error():
    respx.get(f"{WIKI_BASE}/Bad_topic").mock(
        side_effect=RuntimeError("connection reset")
    )
    result = research_topic("Bad topic")
    assert "Research error" in result
    assert "connection reset" in result


@respx.mock
def test_topic_with_leading_trailing_spaces():
    respx.get(f"{WIKI_BASE}/Gravity").mock(
        return_value=httpx.Response(200, json={"extract": "Gravity is a force."})
    )
    result = research_topic("  Gravity  ")
    assert "Gravity" in result


@respx.mock
def test_topic_with_special_characters():
    """Topics like 'Schrödinger's cat' get space→underscore conversion."""
    respx.get(f"{WIKI_BASE}/Schrödinger's_cat").mock(
        return_value=httpx.Response(200, json={"extract": "A thought experiment."})
    )
    result = research_topic("Schrödinger's cat")
    assert "thought experiment" in result


@respx.mock
def test_response_with_redirect():
    """Wikipedia may redirect — httpx follow_redirects=True handles it."""
    respx.get(f"{WIKI_BASE}/USA").mock(
        return_value=httpx.Response(
            200, json={"extract": "The United States of America."}
        )
    )
    result = research_topic("USA")
    assert "United States" in result


@respx.mock
def test_whitespace_only_extract_treated_as_empty():
    respx.get(f"{WIKI_BASE}/Whitespace").mock(
        return_value=httpx.Response(200, json={"extract": "   \n  "})
    )
    result = research_topic("Whitespace")
    assert "200" in result
