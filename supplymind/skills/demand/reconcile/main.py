"""
Demand Reconciliation Skill — main implementation.

Ensures multi-level demand forecasts are consistent (sum to the same total).
Supports three reconciliation approaches:
- Top-down: Disaggregate a top-level forecast proportionally
- Bottom-up: Aggregate bottom-level forecasts and adjust top-down
- Middle-out: Combine both approaches from an anchor level
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np

from supplymind.skills.demand.reconcile.schema import (
    ReconcileInput,
    ReconcileOutput,
    ReconciledForecast,
)

logger = logging.getLogger(__name__)


class DemandReconcile:
    """Multi-level demand reconciliation.

    Ensures that forecasts at different aggregation levels are consistent.
    """

    def run(self, input_data: ReconcileInput | dict) -> ReconcileOutput:
        """Run demand reconciliation."""
        if isinstance(input_data, dict):
            params = ReconcileInput(**input_data)
        else:
            params = input_data

        method = params.method

        if method == "top_down":
            result = self._reconcile_top_down(params)
        elif method == "middle_out":
            result = self._reconcile_middle_out(params)
        else:
            result = self._reconcile_bottom_up(params)

        return result

    def _reconcile_top_down(self, params: ReconcileInput) -> ReconcileOutput:
        """Top-down: disaggregate top-level forecast to children."""
        if params.top_level_forecast is None:
            return ReconcileOutput(
                reconciled=[],
                summary={"error": "top_level_forecast required for top-down method"},
                generated_at=date.today().isoformat(),
            )

        top_target = params.top_level_forecast
        bottom = params.bottom_level
        hierarchy = params.hierarchy
        weights = params.weights or {}

        reconciled: list[ReconciledForecast] = []

        # Add top level
        reconciled.append(ReconciledForecast(
            entity_id="__top__",
            original_value=top_target,
            reconciled_value=top_target,
            adjustment_pct=0.0,
            level="top",
        ))

        # Compute original bottom sum
        original_bottom_sum = sum(item.get("forecast", item.get("value", 0)) for item in bottom)

        # Allocate top target to bottom items
        for item in bottom:
            eid = item.get("entity_id", item.get("sku_id", item.get("id", "")))
            orig_val = item.get("forecast", item.get("value", 0))

            # Determine weight
            w = weights.get(eid, None)
            if w is not None:
                weight = w
            elif original_bottom_sum > 0:
                weight = orig_val / original_bottom_sum
            else:
                weight = 1.0 / len(bottom) if bottom else 0

            reconciled_val = top_target * weight
            adj_pct = ((reconciled_val - orig_val) / orig_val * 100) if orig_val > 0 else 100.0

            reconciled.append(ReconciledForecast(
                entity_id=str(eid),
                original_value=orig_val,
                reconciled_value=round(reconciled_val, 2),
                adjustment_pct=round(adj_pct, 2),
                level="bottom",
            ))

        new_bottom_sum = sum(r.reconciled_value for r in reconciled if r.level == "bottom")

        summary = {
            "method": "top_down",
            "top_level_target": top_target,
            "original_bottom_total": round(original_bottom_sum, 2),
            "reconciled_bottom_total": round(new_bottom_sum, 2),
            "discrepancy": round(abs(top_target - original_bottom_sum), 2),
            "items_reconciled": len(reconciled) - 1,  # exclude top
        }

        return ReconcileOutput(
            reconciled=reconciled,
            summary=summary,
            generated_at=date.today().isoformat(),
        )

    def _reconcile_bottom_up(self, params: ReconcileInput) -> ReconcileOutput:
        """Bottom-up: aggregate bottom-level and adjust proportions."""
        bottom = params.bottom_level
        hierarchy = params.hierarchy

        reconciled: list[ReconciledForecast] = []
        bottom_items = {}

        for item in bottom:
            eid = item.get("entity_id", item.get("sku_id", item.get("id", "")))
            val = item.get("forecast", item.get("value", 0))
            bottom_items[str(eid)] = val
            reconciled.append(ReconciledForecast(
                entity_id=str(eid),
                original_value=val,
                reconciled_value=round(val, 2),
                adjustment_pct=0.0,
                level="bottom",
            ))

        # Build aggregates using hierarchy
        parent_sums = {}
        for parent_id, child_ids in hierarchy.items():
            parent_sum = sum(bottom_items.get(str(cid), 0) for cid in child_ids)
            parent_sums[str(parent_id)] = parent_sum

            reconciled.append(ReconciledForecast(
                entity_id=str(parent_id),
                original_value=round(parent_sum, 2),
                reconciled_value=round(parent_sum, 2),
                adjustment_pct=0.0,
                level="middle",
            ))

        # Grand total
        grand_total = sum(parent_sums.values()) if parent_sums else sum(bottom_items.values())
        if not parent_sums:
            grand_total = sum(bottom_items.values())

        reconciled.insert(0, ReconciledForecast(
            entity_id="__grand_total__",
            original_value=round(grand_total, 2),
            reconciled_value=round(grand_total, 2),
            adjustment_pct=0.0,
            level="top",
        ))

        # If there's a top-level target, apply proportional adjustment
        if params.top_level_forecast and abs(grand_total - params.top_level_forecast) > 1e-6:
            ratio = params.top_level_forecast / grand_total
            for r in reconciled:
                r.reconciled_value = round(r.original_value * ratio, 2)
                r.adjustment_pct = round((ratio - 1) * 100, 2)

        summary = {
            "method": "bottom_up",
            "bottom_items": len(bottom_items),
            "aggregation_levels": len(set(hierarchy.keys())) if hierarchy else 0,
            "grand_total": round(reconciled[0].reconciled_value, 2) if reconciled else 0,
            "adjusted": params.top_level_forecast is not None,
        }

        return ReconcileOutput(
            reconciled=reconciled,
            summary=summary,
            generated_at=date.today().isoformat(),
        )

    def _reconcile_middle_out(self, params: ReconcileInput) -> ReconcileOutput:
        """Middle-out: combine top-down and bottom-up from an anchor level."""
        # Run both methods
        td_result = self._reconcile_top_down(params)
        bu_result = self._reconcile_bottom_up(params)

        # For middle-out, we take bottom-up as base and use top-down ratios for guidance
        reconciled = bu_result.reconciled.copy()

        # Apply smoothing between the two approaches
        alpha = 0.6  # Weight toward bottom-up

        # Merge results by taking weighted average
        td_lookup = {r.entity_id: r for r in td_result.reconciled}
        for r in reconciled:
            if r.entity_id in td_lookup and r.entity_id != "__grand_total__":
                td_val = td_lookup[r.entity_id].reconciled_value
                bu_val = r.reconciled_value
                blended = alpha * bu_val + (1 - alpha) * td_val
                r.reconciled_value = round(blended, 2)
                r.adjustment_pct = round((blended / max(r.original_value, 1e-6) - 1) * 100, 2)

        summary = {
            "method": "middle_out",
            "blend_factor": alpha,
            "items_reconciled": len([r for r in reconciled if r.entity_id != "__grand_total__"]),
            "grand_total": round(next((r.reconciled_value for r in reconciled if r.level == "top"), 0), 2),
        }

        return ReconcileOutput(
            reconciled=reconciled,
            summary=summary,
            generated_at=date.today().isoformat(),
        )
