import os
import json
import asyncio
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Clean CORS for production-ready local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
MODEL_ATTRIBUTION = "gpt-4o"

MEMORY_FILE = Path("student_profile.json")
_file_lock = asyncio.Lock()

DEFAULT_PROFILE = {
    "level": 1,
    "mastered_topics": [],
    "struggles": [],
}


async def load_profile() -> dict:
    async with _file_lock:
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        return DEFAULT_PROFILE.copy()


async def save_profile(profile: dict) -> None:
    async with _file_lock:
        with open(MEMORY_FILE, "w") as f:
            json.dump(profile, f, indent=2)


class QueryRequest(BaseModel):
    topic: str
    age: int = 12


class QueryResponse(BaseModel):
    explanation: str
    model: str
    profile: dict


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/privacy")
async def privacy():
    return FileResponse("privacy.html")


@app.post("/query", response_model=QueryResponse)
async def query_topic(request: QueryRequest):
    if request.age < 5 or request.age > 18:
        raise HTTPException(status_code=400, detail="Age must be between 5 and 18.")

    # Scrape live data from Wikipedia
    wiki_url = f"https://en.wikipedia.org/wiki/{quote(request.topic.replace(' ', '_'))}"
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=wiki_url)
        raw_text = result.markdown[:3000] if result.markdown else ""

    if not raw_text:
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve content for topic '{request.topic}' from Wikipedia.",
        )

    profile = await load_profile()

    system_prompt = (
        "You are an adaptive AI tutor. Reframe the following topic using Singaporean Math, "
        "Estonian Logic, and US Recovery pedagogical frameworks. "
        f"The student is {request.age} years old at level {profile['level']}. "
        f"Mastered topics: {profile['mastered_topics']}. "
        f"Known struggles: {profile['struggles']}. "
        "Keep explanations age-appropriate and fact-checked."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Topic: {request.topic}\n\nSource material:\n{raw_text}"),
    ]

    response = await llm.ainvoke(messages)
    explanation = response.content

    # Update profile memory
    if request.topic not in profile["mastered_topics"]:
        profile["mastered_topics"].append(request.topic)
    await save_profile(profile)

    return QueryResponse(
        explanation=explanation,
        model=MODEL_ATTRIBUTION,
        profile=profile,
    )


@app.get("/profile")
async def get_profile():
    return await load_profile()


@app.post("/profile/reset")
async def reset_profile():
    await save_profile(DEFAULT_PROFILE.copy())
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
