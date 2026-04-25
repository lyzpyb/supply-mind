"""
Inventory Skill Handlers — async bridges for all inventory-related skills.

Covers: reorder, safety_stock, policy_sim, classify, multi_echelon, newsvendor
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Inventory Reorder ─────────────────────────────────────────────────────

INVENTORY_REORDER_TOOL_SPEC = {
    "name": "inventory_reorder",
    "description": (
        "Calculate optimal reorder points and order quantities for SKUs.\n\n"
        "Core inventory optimization tool:\n"
        "- Computes economic order quantity (EOQ)\n"
        "- Calculates reorder point based on demand and lead time\n"
        "- Balances holding costs vs stockout costs\n"
        "- Supports continuous review (R,Q) and periodic review (R,S) policies\n\n"
        "Use AFTER running demand_forecast to get accurate demand parameters."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "skus": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "SKU parameters. Each: {sku_id, unit_cost, holding_cost_rate?, "
                    "stockout_cost?, lead_time_days, demand_rate, current_stock?, order_cost?}"
                ),
            },
            "policy_type": {
                "type": "string",
                "enum": ["continuous", "periodic"],
                "default": "continuous",
                "description": "Inventory policy type",
            },
            "service_level_target": {
                "type": "number",
                "default": 0.95,
                "description": "Target service level (0.8-0.99)",
            },
            "review_period_days": {
                "type": "integer",
                "default": 7,
                "description": "Review period for periodic policy (days)",
            },
        },
        "required": ["skus"],
    },
}


async def inventory_reorder_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for inventory reorder tool."""
    try:
        from supplymind.skills.inventory.reorder.main import InventoryReorder
        from supplymind.skills.inventory.reorder.schema import ReorderInput

        input_data = ReorderInput(
            skus=arguments["skus"],
            policy_type=arguments.get("policy_type", "continuous"),
            service_level_target=arguments.get("service_level_target", 0.95),
            review_period_days=arguments.get("review_period_days", 7),
        )

        skill = InventoryReorder()
        result = await _run_sync(skill.run, input_data)
        return _format_inventory_result(result, "Reorder Point Analysis"), True

    except Exception as e:
        logger.error("Inventory reorder error: %s", e, exc_info=True)
        return f"Inventory reorder error: {e}", False


# ── Safety Stock ───────────────────────────────────────────────────────────

INVENTORY_SAFETY_STOCK_TOOL_SPEC = {
    "name": "inventory_safety_stock",
    "description": (
        "Calculate safety stock levels for target service levels.\n\n"
        "Use this to determine buffer inventory needed:\n"
        "- Accounts for demand variability during lead time\n"
        "- Accounts for supply lead time variability\n"
        "- Supports different service level targets per SKU\n"
        "- Calculates safety stock cost investment\n\n"
        "Complements inventory_reorder by focusing specifically on the safety stock component."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "skus": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "SKU parameters: {sku_id, avg_daily_demand, demand_std, "
                    "lead_time_days, lead_time_std?, unit_value?}"
                ),
            },
            "service_level": {
                "type": "number",
                "default": 0.95,
                "description": "Target service level (0.8-0.99)",
            },
            "include_cost_analysis": {
                "type": "boolean",
                "default": True,
                "description": "Include holding cost analysis for safety stock",
            },
        },
        "required": ["skus"],
    },
}


async def inventory_safety_stock_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for safety stock tool."""
    try:
        from supplymind.skills.inventory.safety_stock.main import SafetyStock
        from supplymind.skills.inventory.safety_stock.schema import SafetyStockInput

        input_data = SafetyStockInput(
            skus=arguments["skus"],
            service_level=arguments.get("service_level", 0.95),
            include_cost_analysis=arguments.get("include_cost_analysis", True),
        )

        skill = SafetyStock()
        result = await _run_sync(skill.run, input_data)
        return _format_inventory_result(result, "Safety Stock Analysis"), True

    except Exception as e:
        return f"Safety stock error: {e}", False


# ── Policy Simulation ─────────────────────────────────────────────────────

INVENTORY_POLICY_SIM_TOOL_SPEC = {
    "name": "inventory_policy_sim",
    "description": (
        "Simulate inventory policies with Monte Carlo methods.\n\n"
        "Use this to COMPARE different inventory policies before implementing:\n"
        "- Simulates (R,Q), (s,S), base-stock policies over time\n"
        "- Uses Monte Carlo with stochastic demand\n"
        "- Measures fill rate, average inventory, stockout events, costs\n"
        "- Compares multiple policies side-by-side with statistical significance\n\n"
        "More detailed than inventory_reorder; use for policy selection decisions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_params": {
                "type": "object",
                "description": (
                    "Target SKU parameters: {sku_id, unit_cost, holding_cost_rate, "
                    "stockout_cost_per_unit, lead_time_days, demand_distribution}"
                ),
            },
            "policies": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Policies to simulate. Each: {name, type, reorder_point, "
                    "order_quantity?, order_up_to_level?}"
                ),
            },
            "simulation_days": {
                "type": "integer",
                "default": 365,
                "description": "Number of days to simulate (default: 365)",
            },
            "num_runs": {
                "type": "integer",
                "default": 500,
                "description": "Monte Carlo runs (default: 500)",
            },
        },
        "required": ["sku_params", "policies"],
    },
}


async def inventory_policy_sim_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for inventory policy simulation tool."""
    try:
        from supplymind.skills.inventory.policy_sim.main import InventoryPolicySim
        from supplymind.skills.inventory.policy_sim.schema import PolicySimInput

        input_data = PolicySimInput(
            sku_params=arguments["sku_params"],
            policies=arguments["policies"],
            simulation_days=arguments.get("simulation_days", 365),
            num_runs=arguments.get("num_runs", 500),
        )

        skill = InventoryPolicySim()
        result = await _run_sync(skill.run, input_data)

        # Format comparison table
        lines = ["# Inventory Policy Simulation Results", ""]
        if hasattr(result, 'comparison') and result.comparison:
            lines.append("## Policy Comparison")
            lines.append("| Policy | Fill Rate | Avg Inventory | Stockouts | Total Cost |")
            lines.append("|--------|-----------|---------------|-----------|------------|")
            comp = result.comparison if hasattr(result.comparison, '__iter__') else [result.comparison]
            for p in (comp if isinstance(comp, list) else [comp]):
                p_dict = p.model_dump() if hasattr(p, 'model_dump') else dict(p)
                lines.append(
                    f"| {p_dict.get('name', 'N/A')} | {p_dict.get('fill_rate', 'N/A')}% | "
                    f"{p_dict.get('avg_inventory', 'N/A')} | {p_dict.get('stockout_events', 'N/A')} | "
                    f"${p_dict.get('total_cost', 'N/A'):,.0f} |"
                )
        
        if hasattr(result, 'best_policy'):
            lines.append(f"\n## Recommended: **{result.best_policy}**")

        if hasattr(result, 'model_dump'):
            lines.append("\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```")
        
        return "\n".join(lines), True

    except Exception as e:
        return f"Policy simulation error: {e}", False


# ── ABC/XYZ Classification ────────────────────────────────────────────────

INVENTORY_CLASSIFY_TOOL_SPEC = {
    "name": "inventory_classify",
    "description": (
        "Classify SKUs by ABC/XYZ analysis for inventory segmentation.\n\n"
        "Use this to segment your inventory portfolio:\n"
        "- ABC: By revenue/value contribution (A=top 80%, B=next 15%, C=bottom 5%)\n"
        "- XYZ: By demand variability/coefficient of variation (X=stable, Y=variable, Z=erratic)\n"
        "- Combines into matrix (AX, AY, AZ, BX, ...) with tailored strategies\n"
        "- Recommends inventory policy per segment\n\n"
        "Run BEFORE setting differentiated inventory policies."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_data": {
                "type": "array",
                "items": {"type": "object"},
                "description": "SKU data: [{sku_id, annual_revenue (or annual_quantity * unit_cost), avg_demand, demand_std}]",
            },
            "abc_thresholds": {
                "type": "object",
                "description": "Custom ABC thresholds: {A: 0.8, B: 0.95} (cumulative revenue %)",
            },
            "xyz_thresholds": {
                "type": "object",
                "description": "Custom XYZ CV thresholds: {X: 0.5, Y: 1.0}",
            },
        },
        "required": ["sku_data"],
    },
}


async def inventory_classify_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for inventory classification tool."""
    try:
        from supplymind.skills.inventory.classify.main import InventoryClassify
        from supplymind.skills.inventory.classify.schema import ClassifyInput

        input_data = ClassifyInput(
            sku_data=arguments["sku_data"],
            abc_thresholds=arguments.get("abc_thresholds"),
            xyz_thresholds=arguments.get("xyz_thresholds"),
        )

        skill = InventoryClassify()
        result = await _run_sync(skill.run, input_data)

        output = "# Inventory Classification (ABC-XYZ)\n\n"
        if hasattr(result, 'model_dump'):
            output += "```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```"
        return output, True

    except Exception as e:
        return f"Inventory classification error: {e}", False


# ── Multi-Echelon ─────────────────────────────────────────────────────────

INVENTORY_MULTI_ECHELON_TOOL_SPEC = {
    "name": "inventory_multi_echelon",
    "description": (
        "Optimize inventory across multi-echelon supply networks.\n\n"
        "Use this for complex supply chains with multiple tiers:\n"
        "- Models factory → DC → store / supplier → warehouse → customer chains\n"
        "- Optimizes safety stock placement at each echelon\n"
        "- Accounts for lead time correlations between echelons\n"
        "- Calculates total network inventory cost and service levels\n\n"
        "Requires network structure definition (nodes, arcs, lead times)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "network": {
                "type": "object",
                "description": (
                    "Network definition: {nodes: [{id, type, holding_cost}], "
                    "arcs: [{from, to, lead_time, transport_cost}]}"
                ),
            },
            "demand_at_nodes": {
                "type": "object",
                "description": "Demand parameters per node: {node_id: {mean, std}}",
            },
            "target_service_level": {
                "type": "number",
                "default": 0.95,
            },
        },
        "required": ["network", "demand_at_nodes"],
    },
}


async def inventory_multi_echelon_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for multi-echelon inventory tool."""
    try:
        from supplymind.skills.inventory.multi_echelon.main import MultiEchelon
        from supplymind.skills.inventory.multi_echelon.schema import MultiEchelonInput

        input_data = MultiEchelonInput(
            network=arguments["network"],
            demand_at_nodes=arguments["demand_at_nodes"],
            target_service_level=arguments.get("target_service_level", 0.95),
        )

        skill = MultiEchelon()
        result = await _run_sync(skill.run, input_data)

        output = "# Multi-Echelon Inventory Optimization\n\n"
        if hasattr(result, 'model_dump'):
            output += "```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```"
        return output, True

    except Exception as e:
        return f"Multi-echelon error: {e}", False


# ── Newsvendor ─────────────────────────────────────────────────────────────

INVENTORY_NEWSVENDOR_TOOL_SPEC = {
    "name": "inventory_newsvendor",
    "description": (
        "Solve newsvendor problems for perishable or seasonal products.\n\n"
        "Use this for single-period or short-life products:\n"
        "- Fresh food, fashion, seasonal merchandise, event goods\n"
        "- Balances underage cost (lost sale) vs overage cost (salvage loss)\n"
        "- Computes optimal order quantity for maximum expected profit\n"
        "- Supports known and uncertain demand distributions\n\n"
        "Different from inventory_reorder which is for repeating/replenishable items."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "product": {
                "type": "object",
                "description": (
                    "Product params: {selling_price, cost, salvage_value?, "
                    "demand_mean, demand_std?}"
                ),
            },
            "demand_distribution": {
                "type": "string",
                "enum": ["normal", "uniform", "empirical"],
                "default": "normal",
                "description": "Demand distribution assumption",
            },
            "objective": {
                "type": "string",
                "enum": ["maximize_profit", "maximize_service_level"],
                "default": "maximize_profit",
            },
        },
        "required": ["product"],
    },
}


async def inventory_newsvendor_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for newsvendor tool."""
    try:
        from supplymind.skills.inventory.newsvendor.main import Newsvendor
        from supplymind.skills.inventory.newsvendor.schema import NewsvendorInput

        input_data = NewsvendorInput(
            product=arguments["product"],
            demand_distribution=arguments.get("demand_distribution", "normal"),
            objective=arguments.get("objective", "maximize_profit"),
        )

        skill = Newsvendor()
        result = await _run_sync(skill.run, input_data)

        output = "# Newsvendor Analysis\n\n"
        if hasattr(result, 'optimal_quantity'):
            output += f"## Optimal Order Quantity: **{result.optimal_quantity}** units\n\n"
        if hasattr(result, 'expected_profit'):
            output += f"Expected Profit: ${result.expected_profit:,.2f}\n"
        if hasattr(result, 'critical_ratio'):
            output += f"Critical Ratio: {result.critical_ratio:.1%}\n"
        if hasattr(result, 'model_dump'):
            output += "\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:2000] + "\n```"
        return output, True

    except Exception as e:
        return f"Newsvendor error: {e}", False


# ── Utility ────────────────────────────────────────────────────────────────

async def _run_sync(func, *args, **kwargs):
    """Run sync function in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


def _format_inventory_result(result: Any, title: str) -> str:
    """Generic formatter for inventory results."""
    lines = [f"# {title}", ""]
    
    if hasattr(result, 'model_dump'):
        data = result.model_dump()
        # Try to extract key metrics
        if isinstance(data, dict):
            for k in ['total_investment', 'avg_fill_rate', 'total_safety_stock',
                       'optimal_quantity', 'expected_profit', 'best_policy']:
                if k in data:
                    v = data[k]
                    if isinstance(v, float):
                        lines.append(f"- **{k}**: {v:,.2f}")
                    else:
                        lines.append(f"- **{k}**: {v}")
        
        lines.append("\n## Full Result")
        lines.append("```json")
        lines.append(json.dumps(data, indent=2, default=str)[:3000])
        lines.append("```")
    
    return "\n".join(lines)
