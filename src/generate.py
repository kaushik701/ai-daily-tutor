"""
generate.py — Calls the Groq API to generate the daily lesson or weekly quiz.

Groq exposes an OpenAI-compatible Chat Completions API, so we use the
`openai` SDK pointed at Groq's endpoint. This keeps the code provider-agnostic.

Validates output with Pydantic; retries once with stricter instructions
if the model returns malformed JSON (more common on open-source models).
"""

from __future__ import annotations

import json
import os
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from .curriculum import Topic

# Groq's strongest models for instruction-following + JSON output as of mid-2026.
# llama-3.3-70b-versatile is the best general-purpose pick on free tier.
# qwen-2.5-32b is a solid alternative if Llama gives weak code examples.
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS = 2000
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class Lesson(BaseModel):
    subject_line: str = Field(..., description="Email subject, max 80 chars")
    one_sentence_summary: str = Field(..., description="The TL;DR in 1 sentence")
    plain_english: str = Field(..., description="The concept in plain English, 2-3 short paragraphs")
    analogy: str = Field(..., description="A concrete analogy or metaphor, 1 paragraph")
    code_example: Optional[str] = Field(None, description="Optional Python code, 5-15 lines")
    code_explanation: Optional[str] = Field(None, description="1-2 sentences explaining the code")
    why_it_matters: str = Field(..., description="Why this comes up in AI Eng interviews, 1 paragraph")
    one_thing_to_remember: str = Field(..., description="The single takeaway, 1 sentence")


class QuizQuestion(BaseModel):
    day_number: int
    topic: str
    question: str
    options: list[str] = Field(..., min_length=4, max_length=4)
    correct_answer: str
    explanation: str


class Quiz(BaseModel):
    subject_line: str
    intro: str
    questions: list[QuizQuestion] = Field(..., min_length=3, max_length=6)


LESSON_SYSTEM_PROMPT = """You are an expert AI/ML educator writing one short daily lesson for a Master's-level
Computer Science student who is job-hunting for AI Engineering and ML Engineering roles.

Style rules (non-negotiable):
- Plain English first. Avoid jargon unless you immediately define it.
- One concrete analogy from everyday life (cooking, sports, driving, music, etc.).
- If the concept has a worked code example that fits in 5-15 lines of Python, include it.
- Keep the entire lesson under ~350 words total across all fields.
- Never invent benchmark numbers or paper citations you aren't sure of.
- The "why it matters" section should reference specific AI Eng JD signals: RAG, agents,
  evals, fine-tuning, observability, MCP, production concerns.

CRITICAL OUTPUT FORMAT:
Return ONLY a single valid JSON object. No prose before or after. No markdown code fences.
Start your response with { and end with }. All string values must use double quotes and
escape any internal double quotes with backslash.
"""

LESSON_USER_TEMPLATE = """Today is day {day} of 90 in the curriculum (phase: {phase}).

Topic: {topic}
Difficulty: {difficulty}
Focus this lesson on: {focus}
Interview angle: {interview_angle}

Generate the lesson now as a JSON object with EXACTLY these keys:
- subject_line (string, starts with "Day {day}: ")
- one_sentence_summary (string)
- plain_english (string, 2-3 paragraphs separated by \\n\\n)
- analogy (string, 1 paragraph)
- code_example (string or null, Python code)
- code_explanation (string or null, 1-2 sentences)
- why_it_matters (string, 1 paragraph)
- one_thing_to_remember (string, 1 sentence)

If code does not fit naturally for this topic, use null for both code_example and code_explanation.
"""


QUIZ_SYSTEM_PROMPT = """You are an expert AI/ML educator writing a short weekly quiz for a Master's-level CS student.

Rules:
- Write 4 multiple-choice questions, one per recent lesson.
- Each question tests understanding, not memorization. No trick wording.
- All 4 options should be plausible to someone who half-learned the material.
- The explanation reminds why the right answer is right without being condescending.

CRITICAL OUTPUT FORMAT:
Return ONLY a single valid JSON object. No prose before or after. No markdown fences.
Start with { and end with }.
"""

QUIZ_USER_TEMPLATE = """Generate a weekly quiz covering these recent lessons:

{lessons_summary}

Return a JSON object with EXACTLY these keys:
- subject_line (string): "Week {week} Quiz: How well did you learn?"
- intro (string, 2 sentences)
- questions (array of 4 question objects)

Each question object must have these keys:
- day_number (integer)
- topic (string)
- question (string)
- options (array of EXACTLY 4 strings)
- correct_answer (string, must match one of the options exactly)
- explanation (string, 1-2 sentences)
"""


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a string. Handles markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.startswith("```")]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output: {text[:200]}")
    return json.loads(text[start : end + 1])


def _get_client() -> OpenAI:
    """Build an OpenAI client pointed at Groq."""
    return OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url=GROQ_BASE_URL,
    )


def _call_groq(system_prompt: str, user_prompt: str) -> str:
    """Call Groq via OpenAI-compatible chat completions."""
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


def generate_lesson(topic: Topic) -> Lesson:
    """Generate one daily lesson. Retries once on validation failure."""
    user_prompt = LESSON_USER_TEMPLATE.format(
        day=topic.day,
        phase=topic.phase,
        topic=topic.topic,
        difficulty=topic.difficulty,
        focus=topic.focus,
        interview_angle=topic.interview_angle,
    )

    last_error: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            text = _call_groq(LESSON_SYSTEM_PROMPT, user_prompt)
            data = _extract_json(text)
            return Lesson(**data)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == 1:
                user_prompt += "\n\nIMPORTANT: Your previous response was not valid JSON. Output ONLY the JSON object, no other text."
                continue
    raise ValueError(f"Lesson generation failed after 2 attempts: {last_error}")


def generate_quiz(recent_lessons: list[dict], week: int) -> Quiz:
    """Generate a weekly quiz from the last 4-6 lessons. Retries once on validation failure."""
    lessons_summary = "\n".join(
        f"- Day {l['day_number']}: {l['topic']}" for l in recent_lessons
    )
    user_prompt = QUIZ_USER_TEMPLATE.format(lessons_summary=lessons_summary, week=week)

    last_error: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            text = _call_groq(QUIZ_SYSTEM_PROMPT, user_prompt)
            data = _extract_json(text)
            return Quiz(**data)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == 1:
                user_prompt += "\n\nIMPORTANT: Your previous response was not valid JSON. Output ONLY the JSON object, no other text."
                continue
    raise ValueError(f"Quiz generation failed after 2 attempts: {last_error}")
