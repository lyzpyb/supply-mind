"""
Skill Evolution System — tracks and improves Skill performance over time.

Each Skill maintains an evolution.yaml-like record:
- Method performance tracking (by category/sku)
- User correction history
- Auto-generated selection rules
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_EVOLUTION_DIR = ".supplymind/evolution"


@dataclass
class MethodPerformance:
    """Performance tracking for one forecasting method."""

    method: str = ""
    total_executions: int = 0
    avg_mape: float = 0.0
    best_mape: float = 999.0
    worst_mape: float = 0.0
    best_for_categories: list[str] = field(default_factory=list)
    worst_for_categories: list[str] = field(default_factory=list)


@dataclass
class UserCorrection:
    """Record of a user correction to a prediction."""

    date: str = ""
    sku_id: str = ""
    category: str = ""
    original_value: float = 0.0
    corrected_value: float = 0.0
    reason: str = ""
    learned: str = ""  # What was learned from this correction


@dataclass
class AutoRule:
    """Automatically generated selection rule."""

    rule_id: str = ""
    condition: str = ""          # e.g., "category == 'dairy'"
    action: str = ""             # e.g., "use method 'ema'"
    confidence: float = 0.0      # Rule confidence (based on evidence)
    evidence_count: int = 0
    created_at: str = ""
    last_applied_at: str = ""


@dataclass
class SkillEvolutionProfile:
    """Evolution profile for one Skill."""

    skill_name: str = ""
    total_executions: int = 0
    last_updated: str = ""
    method_performance: dict[str, MethodPerformance] = field(default_factory=dict)
    user_corrections: list[UserCorrection] = field(default_factory=list)
    auto_rules: list[AutoRule] = field(default_factory=list)


class SkillEvolution:
    """Manages evolution profiles for Skills.

    Each Skill gets its own profile tracking:
    - Which methods work best for which categories
    - What corrections users make
    - Auto-generated rules for method selection
    """

    def __init__(self, storage_dir: str | None = None):
        self.storage_dir = Path(storage_dir or DEFAULT_EVOLUTION_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, SkillEvolutionProfile] = {}

    def get_profile(self, skill_name: str) -> SkillEvolutionProfile:
        """Get or create evolution profile for a skill."""
        if skill_name not in self._profiles:
            self._profiles[skill_name] = self._load_profile(skill_name)
        return self._profiles[skill_name]

    def record_execution(
        self,
        skill_name: str,
        method: str,
        mape: float,
        category: str = "",
        sku_id: str = "",
    ):
        """Record a method execution with its accuracy."""
        profile = self.get_profile(skill_name)
        profile.total_executions += 1
        profile.last_updated = datetime.now().isoformat()

        mp = profile.method_performance.get(method)
        if mp is None:
            mp = MethodPerformance(method=method)
            profile.method_performance[method] = mp

        # Update running stats
        mp.total_executions += 1
        n = mp.total_executions
        old_avg = mp.avg_mape
        mp.avg_mape = old_avg + (mape - old_avg) / n

        if mape < mp.best_mape:
            mp.best_mape = mape
            if category and category not in mp.best_for_categories:
                mp.best_for_categories.append(category)
        if mape > mp.worst_mape:
            mp.worst_mape = mape
            if category and category not in mp.worst_for_categories:
                mp.worst_for_categories.append(category)

        self._save_profile(skill_name, profile)

    def record_correction(
        self,
        skill_name: str,
        sku_id: str,
        category: str,
        original_value: float,
        corrected_value: float,
        reason: str = "",
    ):
        """Record a user correction."""
        profile = self.get_profile(skill_name)
        profile.last_updated = datetime.now().isoformat()

        # Determine what was learned
        pct_diff = 0
        if original_value != 0:
            pct_diff = (corrected_value - original_value) / abs(original_value) * 100

        if pct_diff < -15:
            learned = f"Over-forecasting for {category or sku_id}; reduce by ~{abs(pct_diff):.0f}%"
        elif pct_diff > 15:
            learned = f"Under-forecasting for {category or sku_id}; increase by ~{pct_diff:.0f}%"
        else:
            learned = f"Minor adjustment ({pct_diff:+.1f}%) for {category or sku_id}"

        correction = UserCorrection(
            date=datetime.now().isoformat(),
            sku_id=sku_id,
            category=category,
            original_value=original_value,
            corrected_value=corrected_value,
            reason=reason,
            learned=learned,
        )
        profile.user_corrections.append(correction)

        # Keep only last 200 corrections
        if len(profile.user_corrections) > 200:
            profile.user_corrections = profile.user_corrections[-200:]

        # Check if we should generate/update an auto-rule
        self._check_and_update_rules(profile, category, learned)

        self._save_profile(skill_name, profile)

    def get_best_method(self, skill_name: str, category: str = "") -> str | None:
        """Get the historically best method for a category."""
        profile = self.get_profile(skill_name)

        if not profile.method_performance:
            return None

        # If we have category-specific info, use it
        if category:
            for method, mp in sorted(profile.method_performance.items(), key=lambda x: x[1].avg_mape):
                if category in mp.best_for_categories:
                    return method

        # Otherwise return global best
        best = min(profile.method_performance.values(), key=lambda mp: mp.avg_mape)
        return best.method if best else None

    def get_auto_rules(self, skill_name: str) -> list[AutoRule]:
        """Get active auto-rules for a skill."""
        profile = self.get_profile(skill_name)
        return [r for r in profile.auto_rules if r.confidence >= 0.5]

    def get_evolution_summary(self, skill_name: str) -> dict:
        """Get a summary of evolution state."""
        profile = self.get_profile(skill_name)

        method_summary = {}
        for method, mp in profile.method_performance.items():
            method_summary[method] = {
                "executions": mp.total_executions,
                "avg_mape": round(mp.avg_mape, 2),
                "best_for": mp.best_for_categories[:5],
            }

        return {
            "skill": skill_name,
            "total_executions": profile.total_executions,
            "last_updated": profile.last_updated,
            "methods_tracked": len(profile.method_performance),
            "corrections_received": len(profile.user_corrections),
            "active_rules": len([r for r in profile.auto_rules if r.confidence >= 0.5]),
            "method_performance": method_summary,
        }

    def _check_and_update_rules(self, profile: SkillEvolutionProfile, category: str, learned: str):
        """Check if we have enough evidence to generate/update an auto-rule."""
        # Find existing rule for this category
        existing = None
        for rule in profile.auto_rules:
            if category in rule.condition:
                existing = rule
                break

        # Count corrections for this category
        cat_corrections = [c for c in profile.user_corrections if c.category == category]

        if len(cat_corrections) >= 3:
            # Determine direction
            avg_adj = 0
            for c in cat_corrections[-10:]:
                if c.original_value != 0:
                    avg_adj += (c.corrected_value - c.original_value) / abs(c.original_value)
            avg_adj /= min(len(cat_corrections), 10)

            # Find best method for this category
            best_method = None
            best_mape = 999
            for method, mp in profile.method_performance.items():
                if category in mp.best_for_categories and mp.avg_mape < best_mape:
                    best_mape = mp.avg_mape
                    best_method = method

            if existing:
                existing.evidence_count = len(cat_corrections)
                existing.confidence = min(0.95, 0.3 + len(cat_corrections) * 0.05)
                existing.last_applied_at = datetime.now().isoformat()
            else:
                import uuid
                rule = AutoRule(
                    rule_id=f"rule_{uuid.uuid4().hex[:6]}",
                    condition=f"category == '{category}'",
                    action=f"use method '{best_method or 'auto'}'" if best_method else "apply bias correction",
                    confidence=min(0.7, 0.3 + len(cat_corrections) * 0.05),
                    evidence_count=len(cat_corrections),
                    created_at=datetime.now().isoformat(),
                )
                profile.auto_rules.append(rule)

        # Keep rules manageable
        if len(profile.auto_rules) > 50:
            profile.auto_rules.sort(key=lambda r: r.confidence, reverse=True)
            profile.auto_rules = profile.auto_rules[:50]

    def _load_profile(self, skill_name: str) -> SkillEvolutionProfile:
        """Load profile from disk."""
        path = self.storage_dir / f"{skill_name}_evolution.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Reconstruct from dict
                profile = SkillEvolutionProfile(
                    skill_name=data.get("skill_name", skill_name),
                    total_executions=data.get("total_executions", 0),
                    last_updated=data.get("last_updated", ""),
                )
                for method, mp_data in data.get("method_performance", {}).items():
                    profile.method_performance[method] = MethodPerformance(**mp_data)
                for uc_data in data.get("user_corrections", []):
                    profile.user_corrections.append(UserCorrection(**uc_data))
                for ar_data in data.get("auto_rules", []):
                    profile.auto_rules.append(AutoRule(**ar_data))
                return profile
            except Exception as e:
                logger.warning(f"Failed to load evolution profile for {skill_name}: {e}")

        return SkillEvolutionProfile(skill_name=skill_name)

    def _save_profile(self, skill_name: str, profile: SkillEvolutionProfile):
        """Save profile to disk."""
        path = self.storage_dir / f"{skill_name}_evolution.json"

        data = {
            "skill_name": profile.skill_name,
            "total_executions": profile.total_executions,
            "last_updated": profile.last_updated,
            "method_performance": {},
            "user_corrections": [],
            "auto_rules": [],
        }

        for method, mp in profile.method_performance.items():
            data["method_performance"][method] = {
                "method": mp.method,
                "total_executions": mp.total_executions,
                "avg_mape": mp.avg_mape,
                "best_mape": mp.best_mape,
                "worst_mape": mp.worst_mape,
                "best_for_categories": mp.best_for_categories,
                "worst_for_categories": mp.worst_for_categories,
            }

        for uc in profile.user_corrections:
            data["user_corrections"].append({
                "date": uc.date, "sku_id": uc.sku_id, "category": uc.category,
                "original_value": uc.original_value, "corrected_value": uc.corrected_value,
                "reason": uc.reason, "learned": uc.learned,
            })

        for ar in profile.auto_rules:
            data["auto_rules"].append({
                "rule_id": ar.rule_id, "condition": ar.condition, "action": ar.action,
                "confidence": ar.confidence, "evidence_count": ar.evidence_count,
                "created_at": ar.created_at, "last_applied_at": ar.last_applied_at,
            })

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
