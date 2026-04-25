"""
Learning Loop — main controller for self-improvement.

Orchestrates the feedback → learning → improvement cycle:
1. Collects implicit and explicit feedback from HITL decisions
2. Updates Domain Memory with learned patterns
3. Triggers Skill Evolution (method preference updates, auto-rules)
4. Schedules backtesting for post-mortem accuracy measurement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    IMPLICIT_ADOPT = "implicit_adopt"       # User accepted suggestion as-is
    IMPLICIT_ADJUST = "implicit_adjust"     # User modified the suggestion
    IMPLICIT_SKIP = "implicit_skip"         # User skipped the item
    EXPLICIT_THUMBS_UP = "explicit_thumbs_up"
    EXPLICIT_THUMBS_DOWN = "explicit_thumbs_down"
    EXPLICIT_CORRECTION = "explicit_correction"  # Natural language correction
    BACKTEST_RESULT = "backtest_result"      # Automated backtest feedback


@dataclass
class Feedback:
    """A single feedback event."""

    id: str = ""
    feedback_type: FeedbackType = FeedbackType.IMPLICIT_ADOPT
    skill: str = ""
    sku_id: str = ""
    category: str = ""
    decision_id: str = ""           # Linked HITL session ID
    original_value: float | None = None   # What Agent suggested
    adjusted_value: float | None = None  # What user chose (if adjusted)
    actual_outcome: float | None = None   # Realized value (for backtest)
    reason: str = ""
    timestamp: str = ""
    context: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = f"fb_{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class LearningEvent:
    """Record of a learning action taken."""

    event_type: str = ""              # e.g., "preference_updated", "rule_generated", "backtest_scheduled"
    description: str = ""
    details: dict = field(default_factory=dict)
    timestamp: str = ""


class LearningLoop:
    """Main learning loop controller.

    Connects feedback collection, memory updates, and skill evolution.
    """

    def __init__(self, domain_memory=None):
        """Initialize with optional domain memory reference."""
        self._feedback_history: list[Feedback] = []
        self._learning_events: list[LearningEvent] = []
        self._domain_memory = domain_memory
        self._event_callbacks: list[Callable] = []

    def on_feedback(self, feedback: Feedback) -> LearningEvent:
        """Process a new feedback event and trigger learning.

        This is the main entry point called after each human decision.
        """
        self._feedback_history.append(feedback)

        events = []

        # 1. Update Domain Memory based on feedback type
        mem_event = self._update_memory_from_feedback(feedback)
        if mem_event:
            events.append(mem_event)

        # 2. Check if we should generate an auto-rule
        rule_event = self._check_rule_generation(feedback)
        if rule_event:
            events.append(rule_event)

        # 3. Schedule backtest if appropriate
        bt_event = self._maybe_schedule_backtest(feedback)
        if bt_event:
            events.append(bt_event)

        # Notify listeners
        for cb in self._event_callbacks:
            try:
                for ev in events:
                    cb(ev)
            except Exception:
                pass

        return events[0] if events else LearningEvent(
            event_type="no_action",
            description=f"Feedback {feedback.feedback_type.value} recorded but no learning triggered",
        )

    def _update_memory_from_feedback(self, feedback: Feedback) -> LearningEvent | None:
        """Update domain memory based on feedback content."""
        if not self._domain_memory:
            return None

        dm = self._domain_memory

        if feedback.feedback_type == FeedbackType.IMPLICIT_ADJUST:
            # User adjusted — record parameter preference
            if feedback.sku_id or feedback.category:
                cat = feedback.category or feedback.sku_id
                adjustment_pct = 0
                if feedback.original_value and feedback.original_value != 0:
                    adjustment_pct = ((feedback.adjusted_value or 0) - feedback.original_value) / abs(feedback.original_value) * 100

                # Record that this category tends to be over/under-estimated
                if adjustment_pct < -10:
                    dm.set_preference(f"{cat}_tendency", "overestimate")
                    dm.record_pattern("adjustment_pattern", f"Tends to over-forecast for {cat}", {
                        "category": cat,
                        "avg_adjustment_pct": round(adjustment_pct, 1),
                        "count": 1,
                    })
                elif adjustment_pct > 10:
                    dm.set_preference(f"{cat}_tendency", "underestimate")
                    dm.record_pattern("adjustment_pattern", f"Tends to under-forecast for {cat}", {
                        "category": cat,
                        "avg_adjustment_pct": round(adjustment_pct, 1),
                        "count": 1,
                    })

                return LearningEvent(
                    event_type="preference_updated",
                    description=f"Updated preference for '{cat}' based on adjustment",
                    details={"category": cat, "adjustment_pct": round(adjustment_pct, 1)},
                    timestamp=datetime.now().isoformat(),
                )

        elif feedback.feedback_type == FeedbackType.EXPLICIT_CORRECTION:
            # Explicit correction — high value signal
            dm.record_pattern("explicit_correction", feedback.reason or "User correction recorded", {
                "skill": feedback.skill,
                "sku_id": feedback.sku_id,
                "reason": feedback.reason,
            })

            return LearningEvent(
                event_type="correction_recorded",
                description=f"Explicit correction for {feedback.skill}/{feedback.sku_id}",
                details={"reason": feedback.reason},
                timestamp=datetime.now().isoformat(),
            )

        elif feedback.feedback_type == FeedbackType.BACKTEST_RESULT:
            # Record model performance
            mape = feedback.context.get("mape")
            method = feedback.context.get("method_used")
            category = feedback.category or feedback.sku_id
            if mape is not None and method:
                dm.record_model_performance(category, method, mape, context=feedback.reason)

            return LearningEvent(
                event_type="performance_recorded",
                description=f"Backtest result: {category} MAPE={mape} (method={method})",
                details={"mape": mape, "method": method},
                timestamp=datetime.now().isoformat(),
            )

        return None

    def _check_rule_generation(self, feedback: Feedback) -> LearningEvent | None:
        """Check if enough evidence exists to generate an auto-rule."""
        if feedback.feedback_type not in (
            FeedbackType.IMPLICIT_ADJUST, FeedbackType.EXPLICIT_CORRECTION
        ):
            return None

        # Count similar adjustments for same category
        cat = feedback.category or feedback.sku_id
        similar = [
            f for f in self._feedback_history[-50:]
            if (f.category == cat or f.sku_id == cat)
            and f.feedback_type in (FeedbackType.IMPLICIT_ADJUST, FeedbackType.EXPLICIT_CORRECTION)
        ]

        if len(similar) >= 3:
            # Generate rule suggestion
            avg_adj = 0
            count = 0
            for f in similar:
                if f.original_value and f.original_value != 0:
                    avg_adj += ((f.adjusted_value or 0) - f.original_value) / abs(f.original_value)
                    count += 1

            avg_adj_pct = (avg_adj / count * 100) if count > 0 else 0

            rule_desc = f"For category '{cat}', apply a {'-' if avg_adj_pct < 0 else '+'}{abs(avg_adj_pct):.0f}% adjustment to forecasts"

            if self._domain_memory:
                self._domain_memory.record_pattern("auto_rule", rule_desc, {
                    "category": cat,
                    "avg_adjustment_pct": round(avg_adj_pct, 1),
                    "evidence_count": len(similar),
                    "generated_at": datetime.now().isoformat(),
                })

            return LearningEvent(
                event_type="auto_rule_generated",
                description=rule_desc,
                details={
                    "category": cat,
                    "evidence_count": len(similar),
                    "avg_adjustment_pct": round(avg_adj_pct, 1),
                },
                timestamp=datetime.now().isoformat(),
            )

        return None

    def _maybe_schedule_backtest(self, feedback: Feedback) -> LearningEvent | None:
        """Schedule backtest if we have enough new data."""
        # Schedule backtest every ~20 feedback events
        if len(self._feedback_history) % 20 == 0 and len(self._feedback_history) > 0:
            return LearningEvent(
                event_type="backtest_scheduled",
                description="Backtest recommended (accumulated 20+ feedback events)",
                details={"total_feedback": len(self._feedback_history)},
                timestamp=datetime.now().isoformat(),
            )
        return None

    def get_feedback_summary(self) -> dict:
        """Get summary of all collected feedback."""
        total = len(self._feedback_history)
        by_type = {}
        for fb in self._feedback_history:
            t = fb.feedback_type.value
            by_type[t] = by_type.get(t, 0) + 1

        by_category = {}
        for fb in self._feedback_history:
            cat = fb.category or fb.sku_id or "unknown"
            by_category[cat] = by_category.get(cat, 0) + 1

        adjustments = [fb for fb in self._feedback_history if fb.feedback_type == FeedbackType.IMPLICIT_ADJUST]
        avg_adjustment = 0
        if adjustments:
            vals = [(fb.adjusted_value or 0) - (fb.original_value or 0) for fb in adjustments if fb.original_value]
            if vals:
                avg_adjustment = sum(vals) / len(vals)

        return {
            "total_feedback": total,
            "by_type": by_type,
            "by_category": by_category,
            "total_adjustments": len(adjustments),
            "avg_adjustment": round(avg_adjustment, 2),
            "learning_events": len(self._learning_events),
        }

    def on_learning_event(self, callback: Callable[[LearningEvent], None]):
        """Register callback for learning events."""
        self._event_callbacks.append(callback)
