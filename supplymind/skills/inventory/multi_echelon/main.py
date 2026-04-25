"""
Multi-Echelon Inventory Optimization Skill — main implementation.

Simplified METRIC model for two-level inventory systems.
Computes optimal safety stock placement across factory → DC → Store chain.
"""

from __future__ import annotations

import logging
import math
from datetime import date

import numpy as np
from scipy import stats as sp_stats

from supplymind.skills.inventory.multi_echelon.schema import (
    MultiEchelonInput,
    MultiEchelonOutput,
    EchelonSSResult,
)

logger = logging.getLogger(__name__)


class InventoryMultiEchelon:
    """Multi-echelon inventory optimization.

    Uses a simplified METRIC (Multi-Echelon Technique for Recoverable Item Control)
    approach to determine optimal safety stock placement.
    """

    def run(self, input_data: MultiEchelonInput | dict) -> MultiEchelonOutput:
        """Run multi-echelon optimization."""
        if isinstance(input_data, dict):
            params = MultiEchelonInput(**input_data)
        else:
            params = input_data

        nodes = params.nodes
        if not nodes:
            return MultiEchelonOutput(
                results=[],
                summary={"error": "No nodes provided"},
            )

        sl_target = params.target_service_level
        z_val = abs(sp_stats.norm.ppf(1 - sl_target))

        # Build hierarchy and compute echelon positions
        results: list[EchelonSSResult] = []

        # Compute echelon level (distance from root) for each node
        levels = self._compute_levels(nodes)

        for node in nodes:
            nid = node.node_id
            ntype = node.type
            d_mean = node.demand_mean
            d_std = node.demand_std
            lt = node.lead_time_days
            sl_t = node.service_level_target or sl_target

            # Local safety stock (standard formula)
            z_local = abs(sp_stats.norm.ppf(1 - sl_t))
            local_ss = z_local * d_std * math.sqrt(lt) if lt > 0 else 0

            # Echelon adjustment: higher in the chain needs more buffer
            # because it covers all downstream demand
            echelon_level = levels.get(nid, 0)
            downstream_demand = self._get_downstream_demand(nid, nodes)

            # Echelon SS accounts for cumulative lead time and demand
            cum_lt = self._cumulative_lead_time(nid, nodes)
            echelon_ss = z_local * downstream_demand["std"] * math.sqrt(cum_lt) if cum_lt > 0 else 0

            # Total SS is max of local and echelon considerations
            total_ss = max(local_ss, echelon_ss)
            rop = d_mean * lt + total_ss

            # Achieved SL (approximate based on SS)
            achieved_sl = self._approximate_service_level(d_mean, d_std, lt, total_ss)

            results.append(EchelonSSResult(
                node_id=nid,
                name=node.name or nid,
                type=ntype,
                safety_stock=round(total_ss, 2),
                reorder_point=round(rop, 2),
                local_ss=round(local_ss, 2),
                echelon_ss=round(echelon_ss, 2),
                total_ss=round(total_ss, 2),
                service_level_achieved=round(achieved_sl, 4),
            ))

        # Summary
        total_system_ss = sum(r.total_ss for r in results)
        avg_achieved_sl = np.mean([r.service_level_achieved for r in results]) if results else 0

        summary = {
            "total_nodes": len(nodes),
            "target_service_level": sl_target,
            "avg_achieved_sl": round(avg_achieved_sl, 4),
            "total_system_safety_stock": round(total_system_ss, 2),
            "network_structure": {
                "factories": sum(1 for r in results if r.type == "factory"),
                "dcs": sum(1 for r in results if r.type == "dc"),
                "stores": sum(1 for r in results if r.type == "store"),
            },
        }

        return MultiEchelonOutput(
            results=results,
            summary=summary,
            generated_at=date.today().isoformat(),
        )

    def _compute_levels(self, nodes) -> dict[str, int]:
        """Compute echelon level (depth from root) for each node."""
        node_map = {n.node_id: n for n in nodes}
        levels = {}

        def get_level(node_id, visited=None):
            if visited is None:
                visited = set()
            if node_id in levels:
                return levels[node_id]
            if node_id in visited:
                return 0  # Cycle protection
            visited.add(node_id)

            node = node_map.get(node_id)
            if not node or not node.parent_id:
                levels[node_id] = 0
                return 0
            parent_level = get_level(node.parent_id, visited)
            levels[node_id] = parent_level + 1
            return levels[node_id]

        for n in nodes:
            get_level(n.node_id)

        return levels

    def _get_downstream_demand(self, node_id, nodes) -> dict:
        """Get aggregate demand of this node plus all its descendants."""
        node_map = {n.node_id: n for n in nodes}
        children = [n for n in nodes if n.parent_id == node_id]

        node = node_map.get(node_id)
        my_mean = node.demand_mean if node else 0
        my_std = node.demand_std if node else 0

        child_means = []
        child_stds = []

        for child in children:
            cd = self._get_downstream_demand(child.node_id, nodes)
            child_means.append(cd["mean"])
            child_stds.append(cd["std"])

        total_mean = my_mean + sum(child_means)
        total_std = math.sqrt(my_std ** 2 + sum(s ** 2 for s in child_stds))

        return {"mean": total_mean, "std": total_std}

    def _cumulative_lead_time(self, node_id, nodes) -> float:
        """Sum of lead times along the path to this node."""
        node_map = {n.node_id: n for n in nodes}
        total_lt = 0.0
        current = node_id
        visited = set()

        while current and current not in visited:
            visited.add(current)
            node = node_map.get(current)
            if not node:
                break
            total_lt += node.lead_time_days
            current = node.parent_id

        return total_lt

    @staticmethod
    def _approximate_service_level(d_mean, d_std, lt, ss) -> float:
        """Approximate achieved service level given SS."""
        if d_std < 1e-6 or lt <= 0:
            return 1.0
        z = ss / (d_std * math.sqrt(lt))
        # P(Z <= z) using normal CDF approximation
        try:
            return float(sp_stats.norm.cdf(z))
        except Exception:
            return min(1.0, max(0.0, 0.5 + z * 0.4))
