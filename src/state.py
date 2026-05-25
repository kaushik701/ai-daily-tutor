"""
state.py — Persistent state for the AI Daily Tutor.

Tracks which curriculum day we're on, what was sent, and quiz responses.
SQLite lives in the repo at data/state.db (committed = portable, recruiter-visible).

Design notes:
- Single-writer (GitHub Actions cron), so SQLite is fine; no Postgres needed.
- Schema kept tiny on purpose. v2 (MCP server) will add an `eval_runs` table.
- All timestamps stored as ISO-8601 UTC strings for readability in git diffs.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "state.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sent_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_number INTEGER NOT NULL,
    topic TEXT NOT NULL,
    sent_at_utc TEXT NOT NULL,
    kind TEXT NOT NULL,  -- 'lesson' or 'quiz'
    subject TEXT NOT NULL,
    html_path TEXT,       -- where the rendered email was archived
    UNIQUE(day_number, kind)
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_email_id INTEGER NOT NULL,
    day_number INTEGER NOT NULL,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT NOT NULL,
    FOREIGN KEY (quiz_email_id) REFERENCES sent_emails(id)
);
"""


@dataclass
class SentEmail:
    day_number: int
    topic: str
    sent_at_utc: str
    kind: str
    subject: str


@contextmanager
def get_conn():
    """Context manager that creates the data dir + schema on first use."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_next_lesson_day() -> int:
    """Return the next lesson day to send (1-indexed). Caps at 90."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(day_number) AS max_day FROM sent_emails WHERE kind = 'lesson'"
        ).fetchone()
        last_day = row["max_day"] if row and row["max_day"] is not None else 0
        return min(last_day + 1, 90)


def already_sent_today(kind: str) -> bool:
    """Check if a lesson or quiz was already sent in the last 12 hours.

    Defensive: protects against double-sends if GitHub Actions retries the workflow.
    """
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT sent_at_utc FROM sent_emails
            WHERE kind = ?
            ORDER BY id DESC LIMIT 1
            """,
            (kind,),
        ).fetchone()
        if not row:
            return False
        last = datetime.fromisoformat(row["sent_at_utc"])
        delta = datetime.now(timezone.utc) - last
        return delta.total_seconds() < 12 * 3600


def record_lesson(day_number: int, topic: str, subject: str, html_path: Optional[str]) -> int:
    """Record a sent lesson. Returns the new row id."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO sent_emails (day_number, topic, sent_at_utc, kind, subject, html_path)
            VALUES (?, ?, ?, 'lesson', ?, ?)
            """,
            (
                day_number,
                topic,
                datetime.now(timezone.utc).isoformat(),
                subject,
                html_path,
            ),
        )
        return cur.lastrowid


def record_quiz(
    week_number: int,
    subject: str,
    html_path: Optional[str],
    questions: list[dict],
) -> int:
    """Record a sent quiz and its questions. Quizzes use day_number = -week_number."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO sent_emails (day_number, topic, sent_at_utc, kind, subject, html_path)
            VALUES (?, ?, ?, 'quiz', ?, ?)
            """,
            (
                -week_number,
                f"Week {week_number} quiz",
                datetime.now(timezone.utc).isoformat(),
                subject,
                html_path,
            ),
        )
        quiz_id = cur.lastrowid
        for q in questions:
            conn.execute(
                """
                INSERT INTO quiz_questions
                    (quiz_email_id, day_number, topic, question, correct_answer, explanation)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    quiz_id,
                    q["day_number"],
                    q["topic"],
                    q["question"],
                    q["correct_answer"],
                    q["explanation"],
                ),
            )
        return quiz_id


def get_last_n_lessons(n: int) -> list[dict]:
    """Fetch the last N lessons for use in quiz generation."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT day_number, topic, subject
            FROM sent_emails
            WHERE kind = 'lesson'
            ORDER BY day_number DESC
            LIMIT ?
            """,
            (n,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_week_number() -> int:
    """Approximate week number based on lessons sent. Week 1 = lessons 1-6."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM sent_emails WHERE kind = 'lesson'"
        ).fetchone()
        n_lessons = row["n"] if row else 0
        return (n_lessons // 6) + 1
