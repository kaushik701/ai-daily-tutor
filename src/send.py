"""
send.py — Renders HTML templates and sends emails via Resend.

Archives every rendered email to examples/sent/ so the GitHub repo doubles
as a public archive recruiters can browse.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .generate import Lesson, Quiz

TEMPLATES_DIR = Path(__file__).parent / "templates"
ARCHIVE_DIR = Path(__file__).parent.parent / "examples" / "sent"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)


def render_lesson(lesson: Lesson, day: int, phase: str, github_repo: str) -> str:
    template = _env.get_template("lesson.html.j2")
    return template.render(lesson=lesson, day=day, phase=phase, github_repo=github_repo)


def render_quiz(quiz: Quiz, week: int, github_repo: str) -> str:
    template = _env.get_template("quiz.html.j2")
    return template.render(quiz=quiz, week=week, github_repo=github_repo)


def archive_email(html: str, kind: str, identifier: str) -> str:
    """Save the rendered email to examples/sent/ for the public archive.

    Returns the path relative to repo root.
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{date_str}_{kind}_{identifier}.html"
    path = ARCHIVE_DIR / filename
    path.write_text(html, encoding="utf-8")
    return str(path.relative_to(Path(__file__).parent.parent))


def lesson_to_plain_text(lesson: Lesson, day: int) -> str:
    """Plain-text fallback for email clients that don't render HTML."""
    parts = [
        f"AI Daily Tutor — Day {day} of 90",
        f"{lesson.subject_line}",
        "",
        f"TL;DR: {lesson.one_sentence_summary}",
        "",
        "In plain English:",
        lesson.plain_english,
        "",
        "Think of it this way:",
        lesson.analogy,
        "",
    ]
    if lesson.code_example:
        parts += ["In code:", lesson.code_example, ""]
        if lesson.code_explanation:
            parts += [lesson.code_explanation, ""]
    parts += [
        "Why it matters for AI Eng interviews:",
        lesson.why_it_matters,
        "",
        f"One thing to remember: {lesson.one_thing_to_remember}",
    ]
    return "\n".join(parts)


def quiz_to_plain_text(quiz: Quiz, week: int) -> str:
    """Plain-text fallback for quizzes."""
    parts = [f"AI Daily Tutor — Week {week} Quiz", quiz.subject_line, "", quiz.intro, ""]
    for i, q in enumerate(quiz.questions, 1):
        parts += [
            f"Q{i} (Day {q.day_number} — {q.topic})",
            q.question,
        ]
        for j, opt in enumerate(q.options):
            parts.append(f"  {chr(65 + j)}. {opt}")
        parts.append("")
    parts.append("--- Answers ---")
    for i, q in enumerate(quiz.questions, 1):
        parts += [f"Q{i}: {q.correct_answer}", f"  {q.explanation}", ""]
    return "\n".join(parts)


def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    plain_text: str,
    sender: Optional[str] = None,
) -> dict:
    """Send via Resend. Returns the Resend response dict.

    Requires RESEND_API_KEY env var. Optional RESEND_FROM env var,
    defaults to Resend's onboarding sender if unset.
    """
    resend.api_key = os.environ["RESEND_API_KEY"]
    from_addr = sender or os.environ.get("RESEND_FROM", "AI Daily Tutor <onboarding@resend.dev>")

    params: dict = {
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": plain_text,
    }
    return resend.Emails.send(params)
