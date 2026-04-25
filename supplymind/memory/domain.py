"""
Domain Memory — project-scoped persistent memory for supply chain specifics.

Stores four types of domain-specific knowledge:
  1. Data profile memory (data characteristics)
  2. Parameter preference memory (user's preferred settings)
  3. Model performance memory (which methods work best)
  4. Anomaly pattern memory (known seasonal/promo patterns)

Persisted to JSON files, isolated by project/scene.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default storage directory
DEFAULT_DOMAIN_DIR = ".supplymind/domain_memory"


class DomainMemory:
    """Persistent, project-isolated domain memory.

    Organized into four categories:
    - data_profile: What the user's data looks like
    - parameter_prefs: User's parameter preferences
    - model_performance: Historical model accuracy by category
    - anomaly_patterns: Known anomalies and patterns
    """

    def __init__(self, project_id: str = "default", storage_dir: str | None = None):
        self.project_id = project_id
        self.storage_dir = Path(storage_dir or DEFAULT_DOMAIN_DIR)
        self._storage_path = self.storage_dir / f"{project_id}.json"
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict:
        """Load existing memory from disk."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load domain memory: {e}")
        return {
            "data_profile": {},
            "parameter_prefs": {},
            "model_performance": {},
            "anomaly_patterns": [],
            "metadata": {
                "project_id": self.project_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "total_entries": 0,
            },
        }

    def _save(self):
        """Persist memory to disk."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._data["metadata"]["updated_at"] = datetime.now().isoformat()
        total = (
            len(self._data.get("data_profile", {}))
            + len(self._data.get("parameter_prefs", {}))
            + len(self._data.get("model_performance", {}))
            + len(self._data.get("anomaly_patterns", {}))
        )
        self._data["metadata"]["total_entries"] = total

        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    # ── Data Profile Memory ──

    def set_data_profile(self, key: str, value: Any):
        """Store a data characteristic. E.g., 'granularity': 'daily'."""
        self._data.setdefault("data_profile", {})[key] = value
        self._save()
        logger.info(f"DomainMemory[{self.project_id}]: data_profile.{key} = {value}")

    def get_data_profile(self, key: str, default=None) -> Any:
        return self._data.get("data_profile", {}).get(key, default)

    # ── Parameter Preference Memory ──

    def set_preference(self, key: str, value: Any):
        """Store user parameter preference. E.g., 'service_level': 0.95."""
        self._data.setdefault("parameter_prefs", {})[key] = value
        self._save()
        logger.info(f"DomainMemory[{self.project_id}]: pref.{key} = {value}")

    def get_preference(self, key: str, default=None) -> Any:
        return self._data.get("parameter_prefs", {}).get(key, default)

    # ── Model Performance Memory ──

    def record_model_performance(
        self,
        sku_category: str,
        method: str,
        mape: float,
        context: str | None = None,
    ):
        """Record how well a method performed for a category."""
        perf = self._data.setdefault("model_performance", {})
        cat_key = sku_category or "unknown"
        if cat_key not in perf:
            perf[cat_key] = {}

        history = perf[cat_key].setdefault(method, [])
        history.append({
            "mape": mape,
            "timestamp": datetime.now().isoformat(),
            "context": context,
        })

        # Keep only last 50 entries per method
        if len(history) > 50:
            perf[cat_key][method] = history[-50:]

        self._save()

    def get_best_method(self, sku_category: str) -> str | None:
        """Get the historically best method for a SKU category."""
        perf = self._data.get("model_performance", {}).get(sku_category, {})
        if not perf:
            return None

        best_method = None
        best_avg_mape = float('inf')

        for method, history in perf.items():
            if not history:
                continue
            avg_mape = sum(h["mape"] for h in history) / len(history)
            if avg_mape < best_avg_mape:
                best_avg_mape = avg_mape
                best_method = method

        return best_method

    # ── Anomaly Pattern Memory ──

    def record_pattern(self, pattern_type: str, description: str, details: dict | None = None):
        """Record an anomaly pattern. E.g., promo spike in June."""
        patterns = self._data.setdefault("anomaly_patterns", [])
        patterns.append({
            "type": pattern_type,
            "description": description,
            "details": details or {},
            "recorded_at": datetime.now().isoformat(),
        })
        # Keep last 100 patterns
        if len(patterns) > 100:
            self._data["anomaly_patterns"] = patterns[-100:]
        self._save()

    def get_patterns(self, pattern_type: str | None = None) -> list[dict]:
        """Retrieve recorded patterns, optionally filtered by type."""
        patterns = self._data.get("anomaly_patterns", [])
        if pattern_type:
            return [p for p in patterns if p.get("type") == pattern_type]
        return list(patterns)

    # ── General ──

    def get_all(self) -> dict:
        """Return all domain memory data."""
        return dict(self._data)

    def clear(self):
        """Clear all domain memory."""
        self._data = {
            "data_profile": {}, "parameter_prefs": {},
            "model_performance": {}, "anomaly_patterns": [],
            "metadata": {"project_id": self.project_id, "cleared_at": datetime.now().isoformat()},
        }
        self._save()

    def summary(self) -> dict:
        """Return a summary of stored memories."""
        return {
            "project_id": self.project_id,
            "storage_path": str(self._storage_path),
            "data_profile_entries": len(self._data.get("data_profile", {})),
            "preference_entries": len(self._data.get("parameter_prefs", {})),
            "method_categories": len(self._data.get("model_performance", {})),
            "pattern_count": len(self._data.get("anomaly_patterns", [])),
            "last_updated": self._data.get("metadata", {}).get("updated_at"),
        }

    def __repr__(self) -> str:
        s = self.summary()
        return f"DomainMemory(project={s['project_id']}, entries={s['pattern_count'] + s['preference_entries']})"
