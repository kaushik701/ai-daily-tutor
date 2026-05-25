"""
send.py — Renders HTML templates and sends emails via Gmail SMTP.

Uses Python's stdlib smtplib + email modules — no third-party dependency.
Requires a Gmail App Password (not your regular password). See SETUP.md.

Archives every rendered email to examples/sent/ so the GitHub repo doubles
as a public archive recruiters can browse.
"""

from __future__ import annotations

import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .generate import Lesson, Quiz

TEMPLATES_DIR = Path(__file__).parent / "templates"
ARCHIVE_DIR = Path(__file__).parent.parent / "examples" / "sent"

# Gmail SMTP server settings (fixed; no need to configure).
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

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
    """Save the rendered email to examples/sent/ for the public archive."""
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
    """Send an HTML+text email via Gmail SMTP.

    Required env vars:
      - GMAIL_ADDRESS: your full Gmail address (e.g. you@gmail.com)
      - GMAIL_APP_PASSWORD: a 16-character Gmail App Password (NOT your normal password)

    Optional env vars:
      - SENDER_NAME: display name for the From header (defaults to "AI Daily Tutor")

    Returns a dict with {status, message_id, to} for parity with the previous
    Resend interface so calling code doesn't change.
    """
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address:
        raise RuntimeError("GMAIL_ADDRESS env var is required.")
    if not app_password:
        raise RuntimeError("GMAIL_APP_PASSWORD env var is required.")

    # Strip whitespace; Gmail App Passwords are often shown with spaces every 4 chars
    # (e.g. "abcd efgh ijkl mnop"). Both forms work, but stripping is safer.
    app_password = app_password.replace(" ", "").strip()

    sender_name = os.environ.get("SENDER_NAME", "AI Daily Tutor")
    from_header = sender or formataddr((sender_name, gmail_address))

    # Build a proper multipart/alternative message: plain text + HTML.
    msg = MIMEMultipart("alternative")
    msg["From"] = from_header
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Connect, STARTTLS, login, send. smtplib raises on any failure.
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        try:
            server.login(gmail_address, app_password)
        except smtplib.SMTPAuthenticationError as e:
            # Make the error message helpful — auth failures are 90% of issues.
            raise RuntimeError(
                "Gmail SMTP authentication failed. Common causes:\n"
                "  1. GMAIL_APP_PASSWORD is your normal Gmail password, not a 16-char App Password.\n"
                "     Generate one at https://myaccount.google.com/apppasswords\n"
                "  2. 2-Step Verification is not enabled on the Google account.\n"
                "     App Passwords require 2FA to be on.\n"
                "  3. GMAIL_ADDRESS doesn't match the account the App Password was generated for.\n"
                f"Original error: {e}"
            ) from e
        server.sendmail(gmail_address, [to], msg.as_string())

    return {
        "status": "sent",
        "message_id": msg["Message-ID"],
        "to": to,
    }
