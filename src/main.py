"""
main.py — Entry point invoked by GitHub Actions cron.

Decision tree:
- If today is Sunday AND week has 4+ lessons sent, send a quiz.
- Otherwise, send the next lesson.
- Cap at day 90; after that, the workflow is a no-op.

CLI flags:
- --dry-run: generate + render + archive, but do not call Resend.
- --force-lesson: send a lesson even if today is Sunday.
- --force-quiz:   send a quiz even if today isn't Sunday.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from .curriculum import get_topic
from .generate import generate_lesson, generate_quiz
from .send import (
    archive_email,
    lesson_to_plain_text,
    quiz_to_plain_text,
    render_lesson,
    render_quiz,
    send_email,
)
from .state import (
    already_sent_today,
    get_last_n_lessons,
    get_next_lesson_day,
    get_week_number,
    record_lesson,
    record_quiz,
)


def is_quiz_day() -> bool:
    """Quizzes go out on Sundays in UTC.

    The cron runs at 18:00 UTC (11 AM Pacific Daylight Time).
    On a Sunday at that time, Pacific is still Sunday morning.
    """
    return datetime.now(timezone.utc).weekday() == 6  # 0=Mon, 6=Sun


def send_daily_lesson(dry_run: bool, recipient: str, github_repo: str) -> int:
    day = get_next_lesson_day()
    if day > 90:
        print("[main] Curriculum complete (day > 90). Nothing to send.")
        return 0

    if already_sent_today("lesson"):
        print(f"[main] A lesson was already sent in the last 12 hours. Skipping.")
        return 0

    topic = get_topic(day)
    print(f"[main] Generating lesson for day {day}: {topic.topic}")
    lesson = generate_lesson(topic)

    html = render_lesson(lesson, day=day, phase=topic.phase, github_repo=github_repo)
    plain = lesson_to_plain_text(lesson, day=day)
    archive_path = archive_email(html, kind="lesson", identifier=f"day{day:02d}")
    print(f"[main] Archived to {archive_path}")

    if dry_run:
        print("[main] --dry-run set; skipping send.")
        return 0

    result = send_email(
        to=recipient,
        subject=lesson.subject_line,
        html=html,
        plain_text=plain,
    )
    print(f"[main] Resend response: {result}")
    record_lesson(day, topic.topic, lesson.subject_line, archive_path)
    print(f"[main] Recorded lesson day {day} in state DB.")
    return 0


def send_weekly_quiz(dry_run: bool, recipient: str, github_repo: str) -> int:
    week = get_week_number()
    recent = get_last_n_lessons(6)
    if len(recent) < 3:
        print(f"[main] Only {len(recent)} lessons sent; not enough for a quiz. Sending lesson instead.")
        return send_daily_lesson(dry_run, recipient, github_repo)

    if already_sent_today("quiz"):
        print(f"[main] A quiz was already sent in the last 12 hours. Skipping.")
        return 0

    print(f"[main] Generating quiz for week {week} on {len(recent)} recent lessons.")
    quiz = generate_quiz(recent, week=week)

    html = render_quiz(quiz, week=week, github_repo=github_repo)
    plain = quiz_to_plain_text(quiz, week=week)
    archive_path = archive_email(html, kind="quiz", identifier=f"week{week:02d}")
    print(f"[main] Archived to {archive_path}")

    if dry_run:
        print("[main] --dry-run set; skipping send.")
        return 0

    result = send_email(
        to=recipient,
        subject=quiz.subject_line,
        html=html,
        plain_text=plain,
    )
    print(f"[main] Resend response: {result}")

    questions_records = [
        {
            "day_number": q.day_number,
            "topic": q.topic,
            "question": q.question,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
        }
        for q in quiz.questions
    ]
    record_quiz(week, quiz.subject_line, archive_path, questions_records)
    print(f"[main] Recorded quiz week {week} in state DB.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-lesson", action="store_true")
    parser.add_argument("--force-quiz", action="store_true")
    args = parser.parse_args()

    recipient = os.environ.get("RECIPIENT_EMAIL")
    if not recipient:
        print("ERROR: RECIPIENT_EMAIL env var not set.", file=sys.stderr)
        return 1

    github_repo = os.environ.get("GITHUB_REPOSITORY", "your-username/ai-daily-tutor")

    if args.force_quiz:
        return send_weekly_quiz(args.dry_run, recipient, github_repo)
    if args.force_lesson:
        return send_daily_lesson(args.dry_run, recipient, github_repo)

    if is_quiz_day():
        return send_weekly_quiz(args.dry_run, recipient, github_repo)
    return send_daily_lesson(args.dry_run, recipient, github_repo)


if __name__ == "__main__":
    sys.exit(main())
