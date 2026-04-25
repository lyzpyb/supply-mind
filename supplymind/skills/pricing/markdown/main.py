"""Pricing Markdown Skill — main implementation."""

from __future__ import annotations

import logging

from supplymind.core.pricing_models import optimize_markdown, MarkdownResult
from supplymind.skills.pricing.markdown.schema import (
    MarkdownInput, MarkdownOutput, MarkdownPhaseSchema,
)

logger = logging.getLogger(__name__)


class PricingMarkdown:
    """Optimize phased markdown (clearance) pricing strategy.

    Finds the optimal sequence of price reductions to maximize revenue
    when clearing inventory under time pressure.
    """

    def run(self, input_data: MarkdownInput | dict) -> MarkdownOutput:
        """Run markdown optimization."""
        if isinstance(input_data, dict):
            params = MarkdownInput(**input_data)
        else:
            params = input_data

        result: MarkdownResult = optimize_markdown(
            current_stock=params.current_stock,
            unit_cost=params.unit_cost,
            original_price=params.original_price,
            elasticity=params.elasticity,
            days_remaining=params.days_remaining,
            daily_base_demand=params.daily_base_demand,
            shelf_life_days=params.shelf_life_days,
            min_price_margin=params.min_price_margin,
        )

        phases = [
            MarkdownPhaseSchema(
                start_day=p.start_day,
                end_day=p.end_day,
                price=p.price,
                expected_demand=p.expected_demand,
                expected_revenue=p.expected_revenue,
                remaining_stock=p.remaining_stock,
            )
            for p in result.phases
        ]

        return MarkdownOutput(
            phases=phases,
            total_expected_revenue=result.total_expected_revenue,
            total_expected_sold=result.total_expected_sold,
            clearance_rate=result.clearance_rate,
            revenue_lift_pct=result.revenue_lift_pct,
            recommended_initial_price=result.recommended_initial_price,
            summary={
                "sku_id": params.sku_id,
                "stock_to_clear": params.current_stock,
                "original_price": params.original_price,
                "unit_cost": params.unit_cost,
                "n_phases": len(phases),
                "days_remaining": params.days_remaining,
            },
        )
