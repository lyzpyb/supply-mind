"""
Demand Decomposition Skill — main implementation.

Decomposes time series into trend, seasonal, and residual components
using STL-like decomposition. Provides seasonality strength analysis.
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np

from supplymind.core.timeseries import stl_decompose, DecompositionResult
from supplymind.skills.demand.decompose.schema import (
    DecomposeInput,
    DecomposeOutput,
    DecompositionComponent,
)

logger = logging.getLogger(__name__)


class DemandDecompose:
    """Demand decomposition Skill.

    Breaks down each SKU's demand history into:
    - Trend: long-term direction (increasing / decreasing / stable)
    - Seasonal: repeating patterns (weekly, monthly, etc.)
    - Residual: irregular noise / anomalies
    """

    def run(self, input_data: DecomposeInput | dict) -> DecomposeOutput:
        """Run decomposition for all SKUs."""
        if isinstance(input_data, dict):
            params = DecomposeInput(**input_data)
        else:
            params = input_data

        # Group by SKU
        sku_groups = self._group_demand(params.demand_history, params.sku_filter, params.location_filter)

        if not sku_groups:
            return DecomposeOutput(
                decompositions=[],
                summary={"error": "No demand data found"},
            )

        all_decomps: list[DecompositionComponent] = []
        strong_seasonality_count = 0
        total_seasonality_strength = 0.0

        for (sku_id, loc_id), records in sku_groups.items():
            quantities = [r["quantity"] for r in sorted(records, key=lambda x: x.get("date", ""))]

            if len(quantities) < 4:
                logger.warning(f"Insufficient data for SKU={sku_id}, skipping")
                continue

            arr = np.array(quantities, dtype=float)

            # Run decomposition
            decomp: DecompositionResult = stl_decompose(arr.tolist(), period=params.period)

            # Analyze trend direction
            trend_arr = np.array(decomp.trend)
            n_trend = len(trend_arr)
            if n_trend >= 3:
                first_third = np.mean(trend_arr[:n_trend // 3])
                last_third = np.mean(trend_arr[-n_trend // 3:])
                change_pct = abs(last_third - first_third) / (abs(first_third) + 1e-6)
                if change_pct < 0.05:
                    trend_dir = "stable"
                elif last_third > first_third:
                    trend_dir = "increasing"
                else:
                    trend_dir = "decreasing"
            else:
                trend_dir = "unknown"

            # Classify seasonality strength
            ss = decomp.seasonality_strength
            if ss >= 0.5:
                sea_type = "strong"
                strong_seasonality_count += 1
            elif ss >= 0.25:
                sea_type = "moderate"
            elif ss > 0.1:
                sea_type = "weak"
            else:
                sea_type = "none"

            # Noise level
            residual_var = np.var(decomp.residual) if decomp.residual else 0
            total_var = np.var(arr) + 1e-6
            noise_level = residual_var / total_var

            total_seasonality_strength += ss

            name = records[0].get("sku_name", sku_id) if records else sku_id

            all_decomps.append(DecompositionComponent(
                sku_id=sku_id,
                location_id=loc_id,
                trend=decomp.trend,
                seasonal=decomp.seasonal,
                residual=decomp.residual,
                seasonality_strength=round(ss, 4),
                period=decomp.period,
                trend_direction=trend_dir,
                seasonality_type=sea_type,
                noise_level=round(noise_level, 4),
            ))

        avg_ss = total_seasonality_strength / len(all_decomps) if all_decomps else 0

        # Summary
        summary = {
            "total_skus": len(all_decomps),
            "avg_seasonality_strength": round(avg_ss, 4),
            "strong_seasonality_skus": strong_seasonality_count,
            "trend_distribution": {
                "increasing": sum(1 for d in all_decomps if d.trend_direction == "increasing"),
                "decreasing": sum(1 for d in all_decomps if d.trend_direction == "decreasing"),
                "stable": sum(1 for d in all_decomps if d.trend_direction == "stable"),
            },
            "seasonality_distribution": {
                "strong": sum(1 for d in all_decomps if d.seasonality_type == "strong"),
                "moderate": sum(1 for d in all_decomps if d.seasonality_type == "moderate"),
                "weak": sum(1 for d in all_decomps if d.seasonality_type == "weak"),
                "none": sum(1 for d in all_decomps if d.seasonality_type == "none"),
            },
        }

        return DecomposeOutput(
            decompositions=all_decomps,
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
