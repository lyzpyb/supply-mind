"""
HITL Feedback Collector — gathers implicit and explicit feedback from human decisions.

Enhanced with:
- Automatic Learning Loop integration
- Feedback aggregation and trend analysis
- Correction pattern detection
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    IMPLICIT_ADOPT = "implicit_adopt"       # User accepted suggestion as-is
    IMPLICIT_ADJUST = "implicit_adjust"     # User modified the suggestion
    IMPLICIT_REJECT = "implicit_reject"     # User skipped/rejected
    EXPLICIT_THUMBS_UP = "explicit_thumbs_up"
    EXPLICIT_THUMBS_DOWN = "explicit_thumbs_down"
    EXPLICIT_COMMENT = "explicit_comment"
    BACKTEST_ACCURACY = "backtest_accuracy"  # Automated accuracy measurement


@dataclass
class FeedbackRecord:
    id: str = ""
    session_id: str = ""
    hitl_session_id: str = ""  # Link to HITL session
    feedback_type: FeedbackType = FeedbackType.IMPLICIT_ADOPT
    skill: str = ""
    sku_id: str = ""
    category: str = ""
    timestamp: str = ""
    original_suggestion: dict | None = None
    user_adjustment: dict | None = None
    original_value: float | None = None
    adjusted_value: float | None = None
    comment: str = ""
    context: dict | None = None


class FeedbackCollector:
    """Collect, store, and analyze human decision feedback.

    Integrates with the Learning Loop to automatically feed corrections
    back into the system for continuous improvement.
    """

    def __init__(self, storage_dir: str = ".supplymind/feedback"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[dict] = []
        self._learning_callback: Callable | None = None
        self._load()

    def set_learning_callback(self, callback: Callable):
        """Set callback for feeding feedback into the learning loop."""
        self._learning_callback = callback

    def _load(self):
        path = self.storage_dir / "feedback_log.jsonl"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self._records.append(json.loads(line))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load feedback log: {e}")

    def _append(self, record_dict: dict):
        self._records.append(record_dict)
        path = self.storage_dir / "feedback_log.jsonl"
        with open(path, "a", encoding="utf-8") as f:
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
        sku_id: str = "",
        category: str = "",
        hitl_session_id: str = "",
        original_value: float | None = None,
        adjusted_value: float | None = None,
    ):
        """Record a feedback event and optionally trigger learning."""
        if isinstance(feedback_type, str):
            feedback_type = FeedbackType(feedback_type)

        record = {
            "id": f"fb_{len(self._records)}_{datetime.now().strftime('%H%M%S')}",
            "session_id": session_id,
            "hitl_session_id": hitl_session_id,
            "feedback_type": feedback_type.value,
            "skill": skill,
            "sku_id": sku_id,
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "original_suggestion": original,
            "user_adjustment": adjustment,
            "original_value": original_value,
            "adjusted_value": adjusted_value,
            "comment": comment,
            "context": context or {},
        }
        self._append(record)
        logger.info(f"Feedback recorded: {feedback_type.value} for {skill} (sku={sku_id})")

        # Trigger learning loop if callback is set
        if self._learning_callback:
            try:
                from supplymind.learning.loop import Feedback as LFeedback, FeedbackType as LFT
                fb = LFeedback(
                    feedback_type=LFT(feedback_type.value),
                    skill=skill,
                    sku_id=sku_id,
                    category=category,
                    decision_id=hitl_session_id,
                    original_value=original_value,
                    adjusted_value=adjusted_value,
                    reason=comment,
                    context=context or {},
                )
                self._learning_callback(fb)
            except Exception as e:
                logger.debug(f"Learning callback failed: {e}")

    def get_recent(self, n: int = 50) -> list[dict]:
        return self._records[-n:]

    def get_for_skill(self, skill: str) -> list[dict]:
        return [r for r in self._records if r.get("skill") == skill]

    def get_for_sku(self, sku_id: str) -> list[dict]:
        return [r for r in self._records if r.get("sku_id") == sku_id]

    def get_adoption_rate(self, skill: str | None = None) -> float:
        records = self.get_for_skill(skill) if skill else self._records
        if not records:
            return 0.0
        adopted = sum(1 for r in records if r.get("feedback_type") in (
            "implicit_adopt", "explicit_thumbs_up",
        ))
        return adopted / len(records)

    def get_adjustment_trends(self, category: str | None = None) -> dict:
        """Analyze adjustment patterns over time."""
        adjustments = [
            r for r in self._records[-200:]
            if r.get("feedback_type") == "implicit_adjust"
            and (category is None or r.get("category") == category)
        ]

        if not adjustments:
            return {"count": 0, "avg_adjustment_pct": 0, "trend": "no_data"}

        pct_changes = []
        for r in adjustments:
            orig = r.get("original_value")
            adj = r.get("adjusted_value")
            if orig is not None and adj is not None and orig != 0:
                pct_changes.append((adj - orig) / abs(orig) * 100)

        if not pct_changes:
            return {"count": len(adjustments), "avg_adjustment_pct": 0, "trend": "no_numeric_data"}

        avg_adj = sum(pct_changes) / len(pct_changes)

        # Determine trend direction
        recent = pct_changes[-10:] if len(pct_changes) >= 10 else pct_changes
        older = pct_changes[:-10] if len(pct_changes) > 10 else []
        if older:
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            if recent_avg - older_avg > 2:
                trend = "increasing_overestimation" if avg_adj < 0 else "increasing_underestimation"
            elif recent_avg - older_avg < -2:
                trend = "decreasing_overestimation" if avg_adj < 0 else "decreasing_underestimation"
            else:
                trend = "stable"
        else:
            trend = "insufficient_history"

        return {
            "count": len(adjustments),
            "avg_adjustment_pct": round(avg_adj, 1),
            "median_adjustment_pct": round(sorted(pct_changes)[len(pct_changes) // 2], 1),
            "trend": trend,
            "recent_count": len(recent),
        }

    def summary(self) -> dict:
        total = len(self._records)
        type_counts: dict[str, int] = {}
        for r in self._records:
            t = r.get("feedback_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        # Per-skill adoption rates
        skills = set(r.get("skill", "") for r in self._records)
        skill_rates = {}
        for s in skills:
            if s:
                rate = self.get_adoption_rate(s)
                skill_rates[s] = round(rate, 3)

        return {
            "total_feedbacks": total,
            "by_type": type_counts,
            "overall_adoption_rate": round(self.get_adoption_rate(), 3),
            "per_skill_adoption": skill_rates,
            "unique_skus_seen": len(set(r.get("sku_id", "") for r in self._records if r.get("sku_id"))),
        }
