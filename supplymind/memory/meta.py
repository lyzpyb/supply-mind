"""
Meta Memory — agent-level, permanent cross-project memory.

Stores:
  - Skill usage statistics (calls, success rate, avg duration)
  - User interaction style preferences (detail level, approval threshold)
  - Cross-project generalized learnings
  - Decision history (for Dashboard display)
  - Global configuration defaults
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_META_PATH = ".supplymind/meta_memory.json"


class MetaMemory:
    """Agent-level persistent meta memory.

    This is the highest-level memory layer that persists across all projects.
    It captures:
    1. **Skill Usage**: Which skills are used most, success rates, performance
    2. **User Style**: How the user prefers to interact (detail level, auto-approve thresholds)
    3. **Learnings**: Generalized insights that apply across projects
    4. **Decision History**: Recent decisions for audit trail and dashboard
    """

    def __init__(self, storage_path: str | None = None):
        self.storage_path = Path(storage_path or DEFAULT_META_PATH)
        self._data = self._load()

    def _load(self) -> dict:
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "skill_usage": {},
            "user_style": {
                "default_detail_level": "normal",       # brief / normal / detailed
                "default_hitl_level": "review",          # auto / review / collaborate
                "auto_approve_threshold": 0.85,         # Auto-approve if confidence > this
                "preferred_output_format": "markdown",   # markdown / json / html
                "language": "en",
            },
            "cross_project_learnings": [],
            "decision_history": [],                      # Recent HITL decisions
            "global_defaults": {
                "service_level": 0.95,
                "forecast_horizon_days": 14,
                "safety_stock_z": 1.96,
            },
            "created_at": datetime.now().isoformat(),
        }

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._data["last_updated"] = datetime.now().isoformat()
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False, default=str)

    # ── Skill Usage Tracking ──

    def record_skill_usage(
        self,
        skill_name: str,
        success: bool = True,
        duration: float = 0.0,
        context: dict | None = None,
    ):
        """Record a skill execution."""
        usage = self._data.setdefault("skill_usage", {}).setdefault(skill_name, {
            "total_calls": 0,
            "successes": 0,
            "failures": 0,
            "total_duration": 0.0,
            "avg_duration": 0.0,
            "success_rate": 1.0,
            "last_used": None,
            "first_used": None,
        })
        usage["total_calls"] += 1
        usage["total_duration"] += duration

        if not usage["first_used"]:
            usage["first_used"] = datetime.now().isoformat()

        if success:
            usage["successes"] += 1
        else:
            usage["failures"] += 1

        # Update running stats
        n = usage["total_calls"]
        usage["success_rate"] = round(usage["successes"] / n, 4) if n > 0 else 1.0
        usage["avg_duration"] = round(usage["total_duration"] / n, 3) if n > 0 else 0.0
        usage["last_used"] = datetime.now().isoformat()

        self._save()
        logger.debug(f"MetaMemory: recorded {skill_name} usage (success={success})")

    def get_skill_stats(self, skill_name: str) -> dict:
        return self._data.get("skill_usage", {}).get(skill_name, {})

    def get_top_skills(self, limit: int = 10) -> list[dict]:
        """Get top skills by usage count."""
        skills = self._data.get("skill_usage", {})
        sorted_skills = sorted(skills.items(), key=lambda x: x[1].get("total_calls", 0), reverse=True)
        return [
            {"skill": name, **stats}
            for name, stats in sorted_skills[:limit]
        ]

    # ── User Style Preferences ──

    def set_user_style(self, key: str, value: Any):
        """Record user interaction preference."""
        self._data.setdefault("user_style", {})[key] = value
        self._save()

    def get_user_style(self, key: str, default=None) -> Any:
        return self._data.get("user_style", {}).get(key, default)

    def get_all_styles(self) -> dict:
        """Get all user style preferences."""
        return dict(self._data.get("user_style", {}))

    # ── Cross-Project Learnings ──

    def add_learning(self, learning: str, source_project: str = "", tags: list[str] | None = None):
        """Add a cross-project learning."""
        entry = {
            "learning": learning,
            "source": source_project,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat(),
        }
        self._data.setdefault("cross_project_learnings", []).append(entry)

        # Keep last 200 learnings
        if len(self._data["cross_project_learnings"]) > 200:
            self._data["cross_project_learnings"] = self._data["cross_project_learnings"][-200:]

        self._save()

    def get_relevant_learnings(self, query: str, limit: int = 5) -> list[dict]:
        """Find relevant learnings by keyword matching."""
        query_lower = query.lower()
        learnings = self._data.get("cross_project_learnings", [])

        scored = []
        for l in learnings:
            text = (l.get("learning", "") + " " + " ".join(l.get("tags", []))).lower()
            score = sum(1 for word in query_lower.split() if word in text)
            if score > 0:
                scored.append((score, l))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    # ── Decision History ──

    def record_decision(
        self,
        decision_id: str,
        skill: str,
        decision_type: str,     # approved / rejected / adjusted
        confidence: float,
        summary: str = "",
        details: dict | None = None,
    ):
        """Record a decision for history/audit trail."""
        entry = {
            "decision_id": decision_id,
            "skill": skill,
            "decision_type": decision_type,
            "confidence": confidence,
            "summary": summary,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._data.setdefault("decision_history", []).insert(0, entry)

        # Keep last 500 decisions
        if len(self._data["decision_history"]) > 500:
            self._data["decision_history"] = self._data["decision_history"][:500]

        self._save()

    def get_recent_decisions(self, limit: int = 20) -> list[dict]:
        """Get recent decisions for dashboard/history view."""
        return self._data.get("decision_history", [])[:limit]

    # ── Global Defaults ──

    def set_global_default(self, key: str, value: Any):
        """Set a global configuration default."""
        self._data.setdefault("global_defaults", {})[key] = value
        self._save()

    def get_global_default(self, key: str, default=None) -> Any:
        return self._data.get("global_defaults", {}).get(key, default)

    # ── General ──

    def get_all(self) -> dict:
        """Return all meta memory data (excluding large lists)."""
        return {
            "skill_usage_count": len(self._data.get("skill_usage", {})),
            "user_style": self._data.get("user_style", {}),
            "learnings_count": len(self._data.get("cross_project_learnings", [])),
            "decisions_count": len(self._data.get("decision_history", [])),
            "global_defaults": self._data.get("global_defaults", {}),
            "created_at": self._data.get("created_at"),
            "last_updated": self._data.get("last_updated"),
        }

    def clear(self):
        """Clear all meta memory."""
        self._data = {"cleared_at": datetime.now().isoformat()}
        self._save()

    def summary(self) -> dict:
        """Return a concise summary."""
        return {
            "storage_path": str(self.storage_path),
            "skills_tracked": len(self._data.get("skill_usage", {})),
            "learnings_stored": len(self._data.get("cross_project_learnings", [])),
            "decisions_recorded": len(self._data.get("decision_history", [])),
            "user_preferences_set": len(self._data.get("user_style", {})),
        }
