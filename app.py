import os
import json
import asyncio
from pathlib import Path
from urllib.parse import quote as url_quote
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Aethel API")

# Restrict origins to trusted domains; defaults to localhost for local development.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
# Maximum characters of scraped source text forwarded to the LLM to stay within
# context-window and token-cost limits.
MAX_SOURCE_TEXT_LENGTH = 4000

llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
MODEL_ATTRIBUTION = f"Aethel Engine ({LLM_MODEL})"
MEMORY_FILE = Path("student_profile.json")
_file_lock = asyncio.Lock()


class LearningRequest(BaseModel):
    topic: str
    student_id: str = "default"


async def load_profile(student_id: str) -> dict:
    async with _file_lock:
        if MEMORY_FILE.exists():
            try:
                data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
                return data.get(student_id, {})
            except (json.JSONDecodeError, OSError):
                return {}
        return {}


async def save_profile(student_id: str, profile: dict) -> None:
    async with _file_lock:
        existing: dict = {}
        if MEMORY_FILE.exists():
            try:
                existing = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {}
        existing[student_id] = profile
        MEMORY_FILE.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
        )


@app.get("/")
async def serve_index():
    index_path = Path("index.html")
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not found")


@app.post("/generate-lesson")
async def generate_lesson(req: LearningRequest):
    profile = await load_profile(req.student_id)
    mastered = profile.get("mastered_topics", [])
    gap_areas = profile.get("gap_areas", [])

    # Scrape authoritative source material
    search_url = (
        f"https://en.wikipedia.org/wiki/{url_quote(req.topic.replace(' ', '_'))}"
    )
    source_text = ""
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=search_url)
            source_text = (result.markdown or "")[:MAX_SOURCE_TEXT_LENGTH]
    except Exception:
        source_text = ""

    context_block = ""
    if mastered:
        context_block += f"Topics this student has already mastered: {', '.join(mastered)}.\n"
    if gap_areas:
        context_block += f"Known knowledge gaps: {', '.join(gap_areas)}.\n"

    source_block = (
        f"\n\nReference material (Wikipedia excerpt):\n{source_text}"
        if source_text
        else ""
    )

    system_prompt = (
        "You are Aethel, the Universal AI Encyclopedia and Adaptive Tutor. "
        "Your pedagogy synthesizes Singaporean CPA (Concrete-Pictorial-Abstract) "
        "methodology, Estonian systemic logic, and Finnish inquiry-based learning. "
        "Every lesson must: (1) open with a concise provenance statement citing the "
        "source material, (2) build from concrete examples to abstract principles, "
        "(3) close with one inquiry question that deepens mastery. "
        "Write clearly for a curious learner. Use only straight quotes and standard "
        "ASCII punctuation."
    )

    human_prompt = (
        f"{context_block}"
        f"Generate a focused lesson on: {req.topic}"
        f"{source_block}"
    )

    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
        )
        lesson_text = response.content
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    # Update student profile
    if req.topic not in mastered:
        mastered.append(req.topic)
    profile["mastered_topics"] = mastered
    profile["gap_areas"] = gap_areas
    await save_profile(req.student_id, profile)

    return {
        "topic": req.topic,
        "lesson": lesson_text,
        "model_attribution": MODEL_ATTRIBUTION,
        "source_url": search_url if source_text else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
