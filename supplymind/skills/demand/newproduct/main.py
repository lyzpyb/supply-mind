"""
New Product Demand Forecasting Skill — main implementation.

Handles cold-start forecasting for newly launched products.
Uses similarity-based methods and product lifecycle growth curves.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta

import numpy as np

from supplymind.skills.demand.newproduct.schema import (
    NewProductInput,
    NewProductOutput,
    NewProductForecast,
)

logger = logging.getLogger(__name__)


# Standard product lifecycle growth curve templates (normalized to first 12 weeks)
GROWTH_CURVE_TEMPLATES = {
    "fast_ramp": [0.3, 0.55, 0.75, 0.88, 0.95, 1.0, 1.02, 1.03, 1.02, 1.01, 1.0, 0.98],
    "normal": [0.15, 0.30, 0.48, 0.63, 0.76, 0.85, 0.92, 0.96, 0.99, 1.0, 1.0, 0.99],
    "slow_burn": [0.08, 0.15, 0.24, 0.34, 0.44, 0.54, 0.64, 0.73, 0.81, 0.88, 0.93, 0.97],
}


class DemandNewProduct:
    """New product (cold-start) demand forecasting.

    Two approaches:
    1. Similarity-based: Find similar existing products and use their patterns
    2. Growth curve: Apply standard product lifecycle curves scaled by category benchmarks
    """

    def run(self, input_data: NewProductInput | dict) -> NewProductOutput:
        """Run new product forecast."""
        if isinstance(input_data, dict):
            params = NewProductInput(**input_data)
        else:
            params = input_data

        if params.method == "growth_curve":
            fcst = self._forecast_growth_curve(params)
        else:
            fcst = self._forecast_similarity(params)

        summary = {
            "sku_id": params.sku_id,
            "method": params.method,
            "total_predicted": round(fcst.total_predicted, 2),
            "confidence_score": round(fcst.confidence_score, 3),
            "horizon_days": params.horizon,
            "similar_products_count": len(fcst.similar_products_used),
        }

        return NewProductOutput(
            forecasts=[fcst],
            summary=summary,
            generated_at=date.today().isoformat(),
        )

    def _forecast_similarity(self, params: NewProductInput) -> NewProductForecast:
        """Forecast based on similar existing products."""
        ref_data = params.reference_history

        if not ref_data:
            # No reference data — use conservative default
            return self._conservative_default(params)

        # Group reference data by SKU
        ref_groups = {}
        for r in ref_data:
            sid = r.get("sku_id", "unknown")
            if sid not in ref_groups:
                ref_groups[sid] = []
            ref_groups[sid].append(r)

        # Compute similarity scores and extract patterns
        similar_skus = []
        avg_daily_pattern = []

        for sku_id, records in ref_groups.items():
            quantities = sorted(records, key=lambda x: x.get("date", ""))
            values = [r["quantity"] for r in quantities]

            if len(values) < 5:
                continue

            arr = np.array(values, dtype=float)

            # Simple similarity: check if same category and compute pattern match
            score = 1.0
            rec_cat = records[0].get("category", "") if records else ""
            if params.category and rec_cat != params.category:
                score *= 0.6  # Penalty for different category

            # Use mean of early period as baseline
            n_early = min(len(values), max(3, len(values) // 4))
            early_mean = np.mean(arr[:n_early]) if n_early > 0 else 1.0

            # Normalize pattern (relative to early mean)
            if early_mean > 0:
                normalized = (arr / early_mean).tolist()
            else:
                normalized = [1.0] * len(arr)

            similar_skus.append({
                "sku_id": sku_id,
                "score": round(score, 3),
                "early_mean": round(float(early_mean), 2),
                "pattern_length": len(normalized),
                "pattern": normalized[:params.horizon],  # Truncate/pad to horizon
            })

        if not similar_skus:
            return self._conservative_default(params)

        # Sort by similarity score
        similar_skus.sort(key=lambda x: x["score"], reverse=True)
        top_similar = [s["sku_id"] for s in similar_skus[:5]]

        # Weighted average of patterns (weighted by similarity score)
        total_weight = sum(s["score"] for s in similar_skus[:5])
        if total_weight == 0:
            total_weight = 1.0

        # Build daily forecasts
        base_demand = np.mean([s["early_mean"] for s in similar_skus[:5]])
        daily_fcsts = []

        start_date = date.today() + timedelta(days=1)

        for day in range(params.horizon):
            # Interpolate from similar product patterns
            weighted_pred = 0.0
            for s in similar_skus[:5]:
                pattern = s["pattern"]
                idx = min(day, len(pattern) - 1) if pattern else 0
                factor = pattern[idx]
                weighted_pred += s["score"] * s["early_mean"] * factor

            pred = weighted_pred / total_weight if total_weight > 0 else base_demand

            # Apply mild growth curve ramp-up for first few weeks
            ramp_factor = min(1.0, (day + 1) / (params.ramp_up_weeks * 7)) if params.ramp_up_weeks > 0 else 1.0
            pred *= ramp_factor

            sigma = pred * 0.4  # High uncertainty for new products
            z = 1.96  # 95% CI

            daily_fcsts.append({
                "date": (start_date + timedelta(days=day)).isoformat(),
                "predicted": round(max(0, pred), 2),
                "lower": round(max(0, pred - z * sigma), 2),
                "upper": round(pred + z * sigma, 2),
            })

        total_pred = sum(d["predicted"] for d in daily_fcsts)

        return NewProductForecast(
            sku_id=params.sku_id,
            method_used="similarity_based",
            daily_forecasts=daily_fcsts,
            total_predicted=round(total_pred, 2),
            confidence_score=0.55,  # Low confidence for new products
            reasoning=f"Based on {len(similar_skus)} similar products in category '{params.category}'. Top matches: {top_similar[:3]}",
            similar_products_used=top_similar,
        )

    def _forecast_growth_curve(self, params: NewProductInput) -> NewProductForecast:
        """Forecast using standard product lifecycle growth curve."""
        template_name = "normal"  # Default template
        template = GROWTH_CURVE_TEMPLATES.get(template_name, GROWTH_CURVE_TEMPLATES["normal"])

        # Scale by expected peak demand
        peak = params.expected_peak_demand or 100.0
        ramp_weeks = max(1, params.ramp_up_weeks)

        daily_fcsts = []
        start_date = date.today() + timedelta(days=1)

        for day in range(params.horizon):
            week_idx = min(day // 7, len(template) - 1)
            intra_week_factor = (day % 7) / 7.0
            week_val = template[week_idx]

            # Interpolate between weeks
            if week_idx < len(template) - 1:
                next_val = template[min(week_idx + 1, len(template) - 1)]
                factor = week_val + (next_val - week_val) * intra_week_factor
            else:
                factor = week_val

            # Scale to peak demand with ramp-up adjustment
            ramp_progress = min(1.0, (day + 1) / (ramp_weeks * 7))
            pred = peak * factor * ramp_progress

            sigma = pred * 0.35
            z = 1.96

            daily_fcsts.append({
                "date": (start_date + timedelta(days=day)).isoformat(),
                "predicted": round(max(0, pred), 2),
                "lower": round(max(0, pred - z * sigma), 2),
                "upper": round(pred + z * sigma, 2),
            })

        total_pred = sum(d["predicted"] for d in daily_fcsts)

        return NewProductForecast(
            sku_id=params.sku_id,
            method_used="growth_curve",
            daily_forecasts=daily_fcsts,
            total_predicted=round(total_pred, 2),
            confidence_score=0.50,
            reasoning=f"Growth curve ({template_name}) scaled to peak={peak:.0f}, ramp={ramp_weeks}w",
            similar_products_used=[],
        )

    def _conservative_default(self, params: NewProductInput) -> NewProductForecast:
        """Conservative fallback when no reference data available."""
        daily_fcsts = []
        start_date = date.today() + timedelta(days=1)
        base = 10.0  # Conservative default

        for day in range(params.horizon):
            ramp = min(1.0, (day + 1) / (params.ramp_up_weeks * 7))
            pred = base * ramp
            sigma = pred * 0.5
            z = 1.96

            daily_fcsts.append({
                "date": (start_date + timedelta(days=day)).isoformat(),
                "predicted": round(max(0, pred), 2),
                "lower": 0.0,
                "upper": round(pred + z * sigma, 2),
            })

        total_pred = sum(d["predicted"] for d in daily_fcsts)

        return NewProductForecast(
            sku_id=params.sku_id,
            method_used="conservative_default",
            daily_forecasts=daily_fcsts,
            total_predicted=round(total_pred, 2),
            confidence_score=0.30,
            reasoning="No reference data available; used conservative default with gradual ramp-up.",
            similar_products_used=[],
        )
