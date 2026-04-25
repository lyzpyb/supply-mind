"""
HITL Feedback Collector — gathers implicit and explicit feedback from human decisions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    IMPLICIT_ADOPT = "implicit_adopt"       # User accepted suggestion as-is
    IMPLICIT_ADJUST = "implicit_adjust"     # User modified the suggestion
    IMPLICIT_REJECT = "implicit_reject"     # User skipped/rejected
    EXPLICIT_THUMBS_UP = "explicit_thumbs_up"
    EXPLICIT_THUMBS_DOWN = "explicit_thumbs_down"
    EXPLICIT_COMMENT = "explicit_comment"


@dataclass
class FeedbackRecord:
    id: str
    session_id: str
    feedback_type: FeedbackType
    skill: str
    timestamp: str
    original_suggestion: dict | None = None
    user_adjustment: dict | None = None
    comment: str = ""
    context: dict | None = None


class FeedbackCollector:
    """Collect and store human decision feedback."""

    def __init__(self, storage_dir: str = ".supplymind/feedback"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[dict] = []
        self._load()

    def _load(self):
        path = self.storage_dir / "feedback_log.jsonl"
        if path.exists():
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self._records.append(json.loads(line))
            except (json.JSONDecodeError, IOError):
                pass

    def _append(self, record_dict: dict):
        self._records.append(record_dict)
        path = self.storage_dir / "feedback_log.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(record_dict, ensure_ascii=False, default=str) + "\n")

    def record(
        self,
        session_id: str,
        feedback_type: FeedbackType | str,
        skill: str,
        original: dict | None = None,
        adjustment: dict | None = None,
        comment: str = "",
        context: dict | None = None,
    ):
        """Record a feedback event."""
        if isinstance(feedback_type, str):
            feedback_type = FeedbackType(feedback_type)

        record = {
            "id": f"fb_{len(self._records)}_{datetime.now().strftime('%H%M%S')}",
            "session_id": session_id,
            "feedback_type": feedback_type.value,
            "skill": skill,
            "timestamp": datetime.now().isoformat(),
            "original_suggestion": original,
            "user_adjustment": adjustment,
            "comment": comment,
            "context": context,
        }
        self._append(record)
        logger.info(f"Feedback recorded: {feedback_type.value} for {skill}")

    def get_recent(self, n: int = 50) -> list[dict]:
        return self._records[-n:]

    def get_for_skill(self, skill: str) -> list[dict]:
        return [r for r in self._records if r.get("skill") == skill]

    def get_adoption_rate(self, skill: str | None = None) -> float:
        records = self.get_for_skill(skill) if skill else self._records
        if not records:
            return 0.0
        adopted = sum(1 for r in records if r.get("feedback_type") in (
            "implicit_adopt", "explicit_thumbs_up",
        ))
        return adopted / len(records)

    def summary(self) -> dict:
        total = len(self._records)
        type_counts: dict[str, int] = {}
        for r in self._records:
            t = r.get("feedback", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_feedbacks": total,
            "by_type": type_counts,
            "overall_adoption_rate": round(self.get_adoption_rate(), 3),
        }
