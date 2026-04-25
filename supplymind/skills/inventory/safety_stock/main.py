"""
Safety Stock Skill — main implementation.

Calculates safety stock and reorder points for each SKU.
"""

from __future__ import annotations

import logging
import numpy as np
from supplymind.core.inventory_models import ss_service_level_full
from supplymind.skills.inventory.safety_stock.schema import (
    SafetyStockInput, SafetyStockOutput, SKUSafetyStock,
)

logger = logging.getLogger(__name__)


class InventorySafetyStock:
    """Calculate safety stock using service level or stochastic methods."""

    def run(self, input_data: SafetyStockInput | dict) -> SafetyStockOutput:
        if isinstance(input_data, dict):
            params = SafetyStockInput(**input_data)
        else:
            params = input_data

        items = params.items
        sl = params.service_level
        method = params.method

        results: list[SKUSafetyStock] = []
        total_ss = 0.0

        for item in items:
            sku_id = item.get("item_id", "")
            demand_values = item.get("demand_values", [])
            lead_time = float(item.get("lead_time_days", 7.0))
            lt_std = float(item.get("lead_time_std", 0.0))

            if not demand_values:
                results.append(SKUSafetyStock(sku_id=sku_id))
                continue

            arr = np.array(demand_values)
            d_mean = float(np.mean(arr))
            d_std = float(np.std(arr))

            if method == "stochastic":
                from supplymind.core.inventory_models import ss_stochastic
                result = ss_stochastic(
                    demand_mean=d_mean, demand_std=d_std,
                    lead_time_mean=lead_time, lead_time_std=lt_std,
                    target_service_level=sl,
                )
                ss_val = result.safety_stock
                rop_val = result.reorder_point
            else:
                result = ss_service_level_full(
                    demand_mean_daily=d_mean,
                    std_demand_daily=d_std,
                    lead_time_mean_days=lead_time,
                    std_lead_time_days=lt_std,
                    target_service_level=sl,
                )
                ss_val = result.safety_stock
                rop_val = result.reorder_point

            total_ss += ss_val
            results.append(SKUSafetyStock(
                sku_id=sku_id,
                safety_stock=round(ss_val, 1),
                reorder_point=round(rop_val, 1),
                avg_daily_demand=round(d_mean, 2),
                std_daily_demand=round(d_std, 2),
                lead_time_days=lead_time,
                service_level=sl,
            ))

        return SafetyStockOutput(
            results=results,
            summary={
                "total_skus": len(results),
                "total_safety_stock": round(total_ss, 1),
                "avg_safety_stock": round(total_ss / max(len(results), 1), 1),
                "service_level": sl,
                "method": method,
            },
        )
