"""
Minimal tests that don't require API access — they verify the curriculum
is well-formed and the rendering pipeline works on a stub lesson.

Real generation tests would call the Claude API; those belong in a
nightly eval workflow, not the unit test suite.
"""

from __future__ import annotations

from src.curriculum import get_topic, load_curriculum
from src.generate import Lesson, Quiz, QuizQuestion
from src.send import render_lesson, render_quiz


def test_curriculum_has_90_days():
    topics = load_curriculum()
    assert len(topics) == 90, f"Expected 90 topics, got {len(topics)}"

    days = [t.day for t in topics]
    assert days == list(range(1, 91)), "Days must be 1..90 with no gaps"


def test_each_topic_has_required_fields():
    for t in load_curriculum():
        assert t.topic, f"Day {t.day} missing topic"
        assert t.focus, f"Day {t.day} missing focus"
        assert t.difficulty in {"beginner", "intermediate", "advanced"}
        assert t.interview_angle, f"Day {t.day} missing interview_angle"
        assert t.phase, f"Day {t.day} missing phase"


def test_get_topic_works():
    t = get_topic(1)
    assert t.day == 1
    assert "Model" in t.topic


def test_lesson_renders():
    stub = Lesson(
        subject_line="Day 1: What is a Model, Anyway?",
        one_sentence_summary="A model is a function that maps inputs to outputs.",
        plain_english="A model is just a math function.\n\nIt takes inputs and produces outputs.",
        analogy="Think of it like a recipe.",
        code_example="def model(x):\n    return 2 * x + 1",
        code_explanation="This is a one-parameter linear model.",
        why_it_matters="Every ML conversation starts here.",
        one_thing_to_remember="A model is a function. The training process picks the function.",
    )
    html = render_lesson(stub, day=1, phase="ML/DL Fundamentals", github_repo="kaushik/ai-daily-tutor")
    assert "Day 1" in html
    assert "What is a Model" in html
    assert "linear model" in html


def test_quiz_renders():
    stub = Quiz(
        subject_line="Week 1 Quiz: How well did you learn?",
        intro="This week covered the basics.",
        questions=[
            QuizQuestion(
                day_number=1,
                topic="What is a Model?",
                question="A model is best described as:",
                options=["A database", "A function", "A dataset", "A loss curve"],
                correct_answer="A function",
                explanation="A model maps inputs to outputs; training picks which function.",
            ),
            QuizQuestion(
                day_number=2,
                topic="Supervised Learning",
                question="Which uses labeled data?",
                options=["Supervised", "Unsupervised", "Both", "Neither"],
                correct_answer="Supervised",
                explanation="Supervised learning requires labels.",
            ),
            QuizQuestion(
                day_number=3,
                topic="Train/Val/Test",
                question="Why do we have a test set?",
                options=[
                    "To train the model",
                    "To pick hyperparameters",
                    "To estimate generalization",
                    "To clean data",
                ],
                correct_answer="To estimate generalization",
                explanation="The test set must stay untouched until final evaluation.",
            ),
        ],
    )
    html = render_quiz(stub, week=1, github_repo="kaushik/ai-daily-tutor")
    assert "Week 1" in html
    assert "Supervised" in html
