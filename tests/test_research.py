"""Tests for agents/research.py — Wikipedia API integration."""

import httpx
import respx
import pytest

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
def test_empty_extract_returns_fallback():
    respx.get(f"{WIKI_BASE}/Empty_page").mock(
        return_value=httpx.Response(200, json={"extract": ""})
    )
    result = research_topic("Empty page")
    assert "general knowledge" not in result or "200" in result


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
