"""
curriculum.py — Loads and indexes the 90-day curriculum from YAML.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CURRICULUM_PATH = Path(__file__).parent.parent / "curriculum" / "curriculum.yaml"


@dataclass
class Topic:
    day: int
    topic: str
    focus: str
    difficulty: str
    interview_angle: str
    phase: str


def load_curriculum() -> list[Topic]:
    """Load the full 90-day curriculum as a flat ordered list."""
    with open(CURRICULUM_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    topics: list[Topic] = []
    phase_map = {
        "phase_1_fundamentals": "ML/DL Fundamentals",
        "phase_2_llm": "LLM Concepts",
        "phase_3_ai_engineering": "AI Engineering",
    }
    for key, label in phase_map.items():
        for entry in data.get(key, []):
            topics.append(
                Topic(
                    day=entry["day"],
                    topic=entry["topic"],
                    focus=entry["focus"],
                    difficulty=entry["difficulty"],
                    interview_angle=entry["interview_angle"],
                    phase=label,
                )
            )

    topics.sort(key=lambda t: t.day)
    return topics


def get_topic(day: int) -> Topic:
    """Get the topic for a specific day (1-indexed)."""
    topics = load_curriculum()
    for t in topics:
        if t.day == day:
            return t
    raise ValueError(f"No topic found for day {day}")
