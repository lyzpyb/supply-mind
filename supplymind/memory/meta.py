"""
Meta Memory — agent-level, permanent cross-project memory.

Stores:
  - Skill usage statistics
  - User interaction style preferences
  - Cross-project generalized learnings
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
    """Agent-level persistent meta memory."""

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
            "user_style": {},
            "cross_project_learnings": [],
            "created_at": datetime.now().isoformat(),
        }

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def record_skill_usage(self, skill_name: str, success: bool = True, duration: float = 0.0):
        """Record a skill execution."""
        usage = self._data.setdefault("skill_usage", {}).setdefault(skill_name, {
            "total_calls": 0,
            "successes": 0,
            "failures": 0,
            "total_duration": 0.0,
            "last_used": None,
        })
        usage["total_calls"] += 1
        usage["total_duration"] += duration
        if success:
            usage["successes"] += 1
        else:
            usage["failures"] += 1
        usage["last_used"] = datetime.now().isoformat()
        self._save()

    def get_skill_stats(self, skill_name: str) -> dict:
        return self._data.get("skill_usage", {}).get(skill_name, {})

    def set_user_style(self, key: str, value: Any):
        """Record user interaction preference."""
        self._data.setdefault("user_style", {})[key] = value
        self._save()

    def get_user_style(self, key: str, default=None) -> Any:
        return self._data.get("user_style", {}).get(key, default)

    def add_learning(self, learning: str, source_project: str = ""):
        """Add a cross-project learning."""
        self._data.setdefault("cross_project_learnings", []).append({
            "learning": learning,
            "source": source_project,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep last 200
        if len(self._data["cross_project_learnings"]) > 200:
            self._data["cross_project_learnings"] = self._data["cross_project_learnings"][-200:]
        self._save()
