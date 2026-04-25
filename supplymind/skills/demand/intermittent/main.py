"""
Intermittent Demand Forecasting Skill — main implementation.

Identifies SKUs with intermittent/lumpy demand patterns and applies
Croston's method variants (Classic, SBA, TSB) for accurate forecasting.
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np

from supplymind.core.timeseries import croston_forecast, ForecastResult
from supplymind.skills.demand.intermittent.schema import (
    IntermittentInput,
    IntermittentOutput,
    IntermittentSKUResult,
)

logger = logging.getLogger(__name__)


class DemandIntermittent:
    """Intermittent demand detection and forecasting.

    Workflow:
    1. Scan all SKUs to detect intermittent patterns (>50% zeros)
    2. For intermittent SKUs: apply Croston's method
    3. For non-intermittent SKUs: flag for standard forecasting
    """

    def run(self, input_data: IntermittentInput | dict) -> IntermittentOutput:
        """Run intermittent demand analysis."""
        if isinstance(input_data, dict):
            params = IntermittentInput(**input_data)
        else:
            params = input_data

        # Group by SKU
        sku_groups = self._group_demand(params.demand_history, params.sku_filter, params.location_filter)

        if not sku_groups:
            return IntermittentOutput(results=[], summary={"error": "No data found"})

        all_results: list[IntermittentSKUResult] = []
        intermittent_count = 0
        standard_count = 0

        for (sku_id, loc_id), records in sku_groups.items():
            quantities = [r["quantity"] for r in sorted(records, key=lambda x: x.get("date", ""))]

            if not quantities:
                continue

            arr = np.array(quantities, dtype=float)
            n = len(arr)

            # Detect intermittency
            zero_ratio = float(np.sum(arr == 0)) / n
            is_intermittent = zero_ratio >= params.zero_threshold

            name = records[0].get("sku_name", sku_id) if records else sku_id

            if is_intermittent or not params.auto_detect:
                # Apply Croston's method
                result: ForecastResult = croston_forecast(
                    arr.tolist(),
                    horizon=params.horizon,
                    variant=params.variant,
                    alpha=params.alpha,
                )

                total_pred = sum(result.predicted)
                lower_total = sum(result.lower) if result.lower else 0
                upper_total = sum(result.upper) if result.upper else total_pred * 2

                rec = "use_croston"
                conf = result.confidence_score
            else:
                # Not intermittent — recommend standard methods
                result = ForecastResult(predicted=[float(np.mean(arr))] * params.horizon)
                total_pred = float(np.mean(arr)) * params.horizon
                lower_total = 0.0
                upper_total = total_pred * 1.5
                rec = "use_standard"
                conf = 0.7
                standard_count += 1

            if is_intermittent:
                intermittent_count += 1

            all_results.append(IntermittentSKUResult(
                sku_id=sku_id,
                location_id=loc_id,
                is_intermittent=is_intermittent,
                zero_ratio=round(zero_ratio, 4),
                non_zero_count=int(np.sum(arr > 0)),
                total_periods=n,
                predicted_daily=round(total_pred / params.horizon, 3) if params.horizon > 0 else 0,
                total_predicted=round(total_pred, 2),
                lower=round(lower_total, 2),
                upper=round(upper_total, 2),
                method_used=result.method_used,
                confidence_score=round(conf, 3),
                recommendation=rec,
            ))

        summary = {
            "total_skus": len(all_results),
            "intermittent_skus": intermittent_count,
            "standard_skus": standard_count,
            "intermittent_pct": round(intermittent_count / len(all_results) * 100, 1) if all_results else 0,
            "variant_used": params.variant,
            "horizon_days": params.horizon,
            "avg_zero_ratio": round(float(np.mean([r.zero_ratio for r in all_results])), 4) if all_results else 0,
        }

        return IntermittentOutput(
            results=all_results,
            summary=summary,
            generated_at=date.today().isoformat(),
        )

    def _group_demand(self, demand_history, sku_filter, location_filter):
        groups = {}
        for record in demand_history:
            sku_id = record.get("sku_id", "")
            loc_id = record.get("location_id", "default")
            if sku_filter and sku_id not in sku_filter:
                continue
            if location_filter and loc_id not in location_filter:
                continue
            key = (sku_id, loc_id)
            if key not in groups:
                groups[key] = []
            groups[key].append(record)
        return groups
