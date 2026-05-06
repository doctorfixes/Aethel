import asyncio
import os
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.memory import read_memory, write_memory
from agents.qa import validate_lesson
from agents.research import research_topic

app = FastAPI(title="Æthel — AI Tutor")

CLAUDE_MD = Path("CLAUDE.md")

_TOOLS = [research_topic, read_memory, write_memory, validate_lesson]


def _build_system_prompt(topic: str, age: int) -> str:
    operating_context = CLAUDE_MD.read_text() if CLAUDE_MD.exists() else ""
    return (
        f"{operating_context}\n\n"
        "---\n\n"
        "You are Æthel, a specialist AI tutor. Your job is to produce a single, "
        "well-structured lesson that is age-appropriate, grounded in a real source, "
        "and personalised to this student's learning history.\n\n"
        "WORKFLOW — follow this order strictly:\n"
        "1. Call `research_topic` to obtain source material.\n"
        "2. Call `read_memory` to retrieve the student's profile.\n"
        "3. Draft the lesson using the pedagogical frameworks in CLAUDE.md, "
        f"calibrated for a {age}-year-old.\n"
        "4. Call `validate_lesson` with the draft and the student's age. "
        "If it returns FAIL, revise and call `validate_lesson` again.\n"
        "5. Call `write_memory` to commit the outcome.\n"
        "6. Return the final, validated lesson as your last message — "
        "no meta-commentary, no preamble.\n\n"
        f"Current topic: {topic!r}  |  Student age: {age}"
    )


class LessonRequest(BaseModel):
    topic: str
    age: int
    student_id: str = "anonymous"


class LessonResponse(BaseModel):
    lesson: str
    student_id: str
    topic: str


@app.post("/generate-lesson", response_model=LessonResponse)
async def generate_lesson(request: LessonRequest) -> LessonResponse:
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="topic must not be empty")
    if not (4 <= request.age <= 18):
        raise HTTPException(status_code=400, detail="age must be between 4 and 18")

    def run_orchestrator() -> str:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        runner = client.beta.messages.tool_runner(
            model="claude-opus-4-7",
            max_tokens=8192,
            thinking={"type": "adaptive"},
            system=_build_system_prompt(request.topic, request.age),
            tools=_TOOLS,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Teach '{request.topic}' to a {request.age}-year-old. "
                        f"Student ID: {request.student_id}."
                    ),
                }
            ],
        )
        final_message = runner.get_final_message()
        text_blocks = [
            block.text for block in final_message.content if block.type == "text"
        ]
        return "\n\n".join(text_blocks).strip()

    lesson_text = await asyncio.to_thread(run_orchestrator)

    return LessonResponse(
        lesson=lesson_text,
        student_id=request.student_id,
        topic=request.topic,
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html_path = Path("index.html")
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>Æthel</h1><p>index.html not found.</p>", status_code=200)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy() -> HTMLResponse:
    html_path = Path("privacy.html")
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>Privacy Policy</h1><p>privacy.html not found.</p>", status_code=200)
