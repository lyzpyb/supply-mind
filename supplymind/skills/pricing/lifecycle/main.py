"""Pricing Lifecycle Skill — main implementation."""

from __future__ import annotations

import logging

from supplymind.core.pricing_models import detect_lifecycle_stage, LifecycleStageResult
from supplymind.skills.pricing.lifecycle.schema import LifecycleInput, LifecycleOutput

logger = logging.getLogger(__name__)

# Stage descriptions for dashboard display
_STAGE_INFO = {
    "introduction": {
        "icon": "🌱",
        "color": "#3b82f6",
        "description": "Product is new to market — building awareness",
        "typical_duration": "4-12 weeks",
        "pricing_strategy": "Penetration (low price for share) or Skimming (high price for early adopters)",
    },
    "growth": {
        "icon": "📈",
        "color": "#16a34a",
        "description": "Rapid sales growth — gaining market traction",
        "typical_duration": "12-36 weeks",
        "pricing_strategy": "Competitive pricing to capture share; avoid frequent discounts",
    },
    "maturity": {
        "icon": "🏔️",
        "color": "#d97706",
        "description": "Sales stabilized at peak level — maximize profit",
        "typical_duration": "26-78 weeks",
        "pricing_strategy": "Defend price point; use targeted promotions; focus on margin",
    },
    "decline": {
        "icon": "📉",
        "color": "#dc2626",
        "description": "Sales declining — manage exit strategy",
        "typical_duration": "Variable",
        "pricing_strategy": "Markdown clearance; bundle with strong items; harvest remaining value",
    },
}


class PricingLifecycle:
    """Detect product lifecycle stage from sales history.

    Uses week-over-week growth patterns to classify products into
    introduction / growth / maturity / decline stages.
    """

    def run(self, input_data: LifecycleInput | dict) -> LifecycleOutput:
        """Run lifecycle detection."""
        if isinstance(input_data, dict):
            params = LifecycleInput(**input_data)
        else:
            params = input_data

        result: LifecycleStageResult = detect_lifecycle_stage(
            weekly_sales=params.weekly_sales,
            weeks_since_launch=params.weeks_since_launch,
        )

        info = _STAGE_INFO.get(result.stage, {})

        return LifecycleOutput(
            stage=result.stage,
            confidence=result.confidence,
            current_week=result.current_week,
            peak_week=result.peak_week,
            peak_volume=result.peak_volume,
            avg_growth_rate=result.avg_growth_rate,
            recent_decline_rate=result.recent_decline_rate,
            pricing_recommendation=result.pricing_recommendation,
            stage_summary={
                "icon": info.get("icon", ""),
                "color": info.get("color", ""),
                "description": info.get("description", ""),
                "typical_duration": info.get("typical_duration", ""),
                "pricing_strategy": info.get("pricing_strategy", ""),
                "sku_id": params.sku_id,
                "category": params.category,
                "total_weeks_observed": result.total_weeks_observed,
            },
        )
