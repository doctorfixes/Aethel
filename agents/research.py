import httpx
from anthropic import beta_tool


@beta_tool
def research_topic(topic: str) -> str:
    """Fetch Wikipedia source content about a topic for use in a lesson.

    Args:
        topic: The educational topic to research (e.g. "photosynthesis", "the water cycle")
    """
    wiki_slug = topic.strip().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_slug}"
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True)
        if r.status_code == 200:
            data = r.json()
            extract = data.get("extract", "").strip()
            if extract:
                return (
                    f"[Source: https://en.wikipedia.org/wiki/{wiki_slug}]\n\n{extract}"
                )
        return f"[Wikipedia returned {r.status_code} for '{topic}' — proceed with general knowledge]"
    except httpx.TimeoutException:
        return f"[Wikipedia request timed out for '{topic}' — proceed with general knowledge]"
    except Exception as exc:
        return f"[Research error for '{topic}': {exc}]"
