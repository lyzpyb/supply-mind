"""
Inventory Reorder Skill — main implementation.

Generates reorder suggestions combining forecasts, safety stock, and current inventory.
This is the primary business output Skill.
"""

from __future__ import annotations

import logging
from typing import Optional
from supplymind.skills.inventory.reorder.schema import (
    ReorderInput, ReorderOutput, ReorderSuggestion,
)

logger = logging.getLogger(__name__)


class InventoryReorder:
    """Generate reorder suggestions based on forecasts and inventory levels."""

    def run(self, input_data: ReorderInput | dict) -> ReorderOutput:
        if isinstance(input_data, dict):
            params = ReorderInput(**input_data)
        else:
            params = input_data

        forecasts = params.forecasts
        inventory = {f"{s.get('sku_id', '')}_{s.get('location_id', '')}": s for s in params.inventory_snapshots}
        sku_info = {s.get('sku_id', ''): s for s in params.sku_master}
        ss_map = {s.get('sku_id', ''): s for s in params.safety_stocks}

        suggestions: list[ReorderSuggestion] = []
        total_cost = 0.0
        total_qty = 0.0
        high_urgency = 0
        needs_reorder = 0

        for fc in forecasts:
            sku_id = fc.get("sku_id", "")
            loc_id = fc.get("location_id", "")
            inv_key = f"{sku_id}_{loc_id}"

            # Get forecast totals
            total_predicted = fc.get("total_predicted", fc.get("avg_daily_predicted", 0) * params.horizon)
            avg_daily = fc.get("avg_daily_predicted", total_predicted / max(params.horizon, 1))
            confidence = fc.get("confidence_score", 0.8)

            # Current inventory
            inv_snap = inventory.get(inv_key, {})
            current_stock = inv_snap.get("available", inv_snap.get("on_hand", 0))
            in_transit = inv_snap.get("in_transit", 0)

            # Safety stock
            ss_item = ss_map.get(sku_id, {})
            ss_val = ss_item.get("safety_stock", avg_daily * 2)  # Default ~2 days SS
            rop = ss_item.get("reorder_point", avg_daily * 7 + ss_val) if ss_item else (avg_daily * 7 + ss_val)

            # SKU info
            sku = sku_info.get(sku_id, {})
            unit_cost = sku.get("unit_cost", 0)
            sku_name = sku.get("name", sku_id)

            # Calculate order quantity
            net_position = current_stock + in_transit
            demand_during_horizon = total_predicted
            gap = demand_during_horizon + ss_val - net_position

            if gap > 0:
                suggested_qty = self._round_to_moq(gap, sku.get("moq"))
                urgency = self._determine_urgency(current_stock, avg_daily, rop, ss_val)
                estimated_cost = suggested_qty * unit_cost
                days_of_stock = current_stock / max(avg_daily, 0.001)

                needs_reorder += 1
                if urgency == "high":
                    high_urgency += 1
                total_cost += estimated_cost
                total_qty += suggested_qty

                reason = self._build_reason(sku_id, current_stock, avg_daily, rop, ss_val, suggested_qty, urgency)

                suggestions.append(ReorderSuggestion(
                    sku_id=sku_id,
                    sku_name=sku_name,
                    location_id=loc_id,
                    current_stock=round(current_stock, 1),
                    forecasted_demand=round(total_predicted, 1),
                    safety_stock=round(ss_val, 1),
                    suggested_order_qty=round(suggested_qty, 0),
                    reorder_point=round(rop, 1),
                    urgency=urgency,
                    estimated_cost=round(estimated_cost, 2),
                    days_of_stock=round(days_of_stock, 1),
                    confidence_score=round(confidence, 3),
                    reason=reason,
                ))
            else:
                days_of_stock = current_stock / max(avg_daily, 0.001)
                suggestions.append(ReorderSuggestion(
                    sku_id=sku_id,
                    sku_name=sku_name,
                    location_id=loc_id,
                    current_stock=round(current_stock, 1),
                    forecasted_demand=round(total_predicted, 1),
                    safety_stock=round(ss_val, 1),
                    suggested_order_qty=0,
                    reorder_point=round(rop, 1),
                    urgency="none",
                    estimated_cost=0,
                    days_of_stock=round(days_of_stock, 1),
                    confidence_score=round(confidence, 3),
                    reason="Current stock ({:.0f}) covers forecasted demand ({:.0f})".format(current_stock, total_predicted),
                ))

        # Sort by urgency then by cost descending
        urgency_order = {"high": 0, "medium": 1, "low": 2, "none": 3}
        suggestions.sort(key=lambda s: (urgency_order.get(s.urgency, 3), -s.estimated_cost))

        return ReorderOutput(
            suggestions=suggestions,
            summary={
                "total_skus": len(suggestions),
                "skus_needing_reorder": needs_reorder,
                "high_urgency_count": high_urgency,
                "total_order_quantity": round(total_qty, 0),
                "total_estimated_cost": round(total_cost, 2),
                "service_level": params.service_level,
                "horizon_days": params.horizon,
            },
        )

    def _round_to_moq(self, qty: float, moq: float | None) -> float:
        """Round up to MOQ if specified."""
        if moq and moq > 0:
            import math
            return math.ceil(qty / moq) * moq
        return qty

    def _determine_urgency(self, stock: float, daily_demand: float, rop: float, ss: float) -> str:
        """Determine reorder urgency level."""
        if stock <= 0:
            return "high"
        days_left = stock / max(daily_demand, 0.001)
        if stock < rop - ss or days_left <= 3:
            return "high"
        elif stock < rop or days_left <= 7:
            return "medium"
        elif stock < rop + ss or days_left <= 14:
            return "low"
        return "none"

    def _build_reason(self, sku_id: str, stock: float, daily: float, rop: float, ss: float, qty: float, urgency: str) -> str:
        """Build human-readable explanation."""
        days_left = stock / max(daily, 0.001)
        if urgency == "high":
            return "[HIGH] Urgent: stock={:.0f}, only {:.1f} days left (ROP={:.0f}), suggest reorder {:.0f}".format(stock, days_left, rop, qty)
        elif urgency == "medium":
            return "[MEDIUM] Attention: stock={:.0f}, {:.1f} days left (near ROP={:.0f}), suggest reorder {:.0f}".format(stock, days_left, rop, qty)
        return "[NORMAL] OK: stock={:.0f}, {:.1f} days left, suggest reorder {:.0f} to maintain safety stock".format(stock, days_left, qty)
