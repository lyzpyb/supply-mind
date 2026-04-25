"""
Newsvendor Model Skill — main implementation.

Solves the classic newsvendor problem for single-period decisions:
- Markdown / clearance pricing
- Perishable goods ordering
- Promotional event stocking

Uses both analytical (normal distribution) and empirical approaches.
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
from scipy import stats as sp_stats

from supplymind.core.inventory_models import newsvendor_optimal_order, NewsvendorResult
from supplymind.skills.inventory.newsvendor.schema import (
    NewsvendorInput,
    NewsvendorOutput,
    NewsvendorItemResult,
)

logger = logging.getLogger(__name__)


class InventoryNewsvendor:
    """Newsvendor model solver.

    For each item, computes the optimal order quantity that maximizes
    expected profit given uncertain demand.
    """

    def run(self, input_data: NewsvendorInput | dict) -> NewsvendorOutput:
        """Run newsvendor optimization."""
        if isinstance(input_data, dict):
            params = NewsvendorInput(**input_data)
        else:
            params = input_data

        all_results: list[NewsvendorItemResult] = []
        total_expected_profit = 0.0

        for item in params.items:
            # Solve newsvendor
            result: NewsvendorResult = newsvendor_optimal_order(
                selling_price=item.selling_price,
                cost=item.cost,
                salvage_value=item.salvage_value,
                demand_mean=item.demand_mean,
                demand_std=item.demand_std,
                demand_distribution=item.demand_history,
            )

            # Sensitivity analysis: how does Q* change with price/cost?
            sensitivity = self._sensitivity_analysis(item)

            all_results.append(NewsvendorItemResult(
                sku_id=item.sku_id or "unknown",
                name=item.name or item.sku_id,
                optimal_quantity=round(result.optimal_quantity, 1),
                critical_ratio=round(result.critical_ratio, 4),
                expected_profit=round(result.expected_profit, 2),
                expected_lost_sales=round(
                    result.expected_profit * (1 - result.critical_ratio) / result.critical_ratio
                    if result.critical_ratio > 0 else 0, 2
                ),
                expected_leftover=max(0, round(
                    result.optimal_quantity - (item.demand_mean or 0), 2
                )),
                stockout_probability=round(result.stockout_probability, 4),
                underage_cost=round(result.underage_cost, 2),
                overage_cost=round(result.overage_cost, 2),
                sensitivity=sensitivity,
            ))

            total_expected_profit += result.expected_profit

        summary = {
            "scenario": params.scenario_name or "newsvendor",
            "items_analyzed": len(all_results),
            "total_expected_profit": round(total_expected_profit, 2),
            "avg_critical_ratio": round(np.mean([r.critical_ratio for r in all_results]), 4) if all_results else 0,
        }

        return NewsvendorOutput(
            results=all_results,
            summary=summary,
            generated_at=date.today().isoformat(),
        )

    @staticmethod
    def _sensitivity_analysis(item) -> dict:
        """Analyze how optimal quantity changes with parameter variations."""
        sens = {}
        base_price = item.selling_price
        base_cost = item.cost
        d_mean = item.demand_mean or 100
        d_std = item.demand_std or (d_mean * 0.2)

        cu = base_price - base_cost   # Underage cost
        co = base_cost - (item.salvage_value or 0)  # Overage cost
        cr_base = cu / (cu + co) if (cu + co) > 0 else 0.5
        q_base = d_mean + sp_stats.norm.ppf(cr_base) * d_std

        # Price sensitivity (+/- 10%)
        for delta in [-0.10, -0.05, 0.05, 0.10]:
            new_price = base_price * (1 + delta)
            cu_new = new_price - base_cost
            cr_new = cu_new / (cu_new + co) if (cu_new + co) > 0 else 0.5
            q_new = d_mean + sp_stats.norm.ppf(cr_new) * d_std
            sens[f"price_{delta:+.0%}"] = round(q_new - q_base, 1)

        # Cost sensitivity (+/- 10%)
        for delta in [-0.10, -0.05, 0.05, 0.10]:
            new_cost = base_cost * (1 + delta)
            cu_new2 = base_price - new_cost
            co_new2 = new_cost - (item.salvage_value or 0)
            cr_new2 = cu_new2 / (cu_new2 + co_new2) if (cu_new2 + co_new2) > 0 else 0.5
            q_new2 = d_mean + sp_stats.norm.ppf(cr_new2) * d_std
            sens[f"cost_{delta:+.0%}"] = round(q_new2 - q_base, 1)

        return sens
