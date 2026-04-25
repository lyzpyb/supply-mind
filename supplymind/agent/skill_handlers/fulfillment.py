"""
Fulfillment Skill Handlers — async bridges for fulfillment skills.

Covers: allocation, routing, wave, capacity
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Inventory Allocation ──────────────────────────────────────────────────

FULFILL_ALLOCATION_TOOL_SPEC = {
    "name": "fulfill_allocation",
    "description": (
        "Allocate inventory across multiple warehouses/customers.\n\n"
        "Use this when demand exceeds supply and you need to decide who gets what:\n"
        "- Fair allocation based on historical share or priority\n"
        "- Profit-maximizing allocation considering margins\n"
        "- Multi-warehouse stock balancing\n"
        "- Handles partial fulfillment and backorder decisions\n\n"
        "Requires current inventory positions and demand requirements."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "inventory_positions": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Available inventory: [{location_id, sku_id, quantity_available}]"
                ),
            },
            "demands": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Demand to fulfill: [{customer_id, sku_id, quantity, priority?, margin?}]"
                ),
            },
            "allocation_method": {
                "type": "string",
                "enum": ["fair_share", "profit_max", "priority", "proportional"],
                "default": "fair_share",
                "description": "Allocation strategy",
            },
            "constraints": {
                "type": "object",
                "description": "Optional constraints: {min_fill_rate, max_distance_km}",
            },
        },
        "required": ["inventory_positions", "demands"],
    },
}


async def fulfill_allocation_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for inventory allocation tool."""
    try:
        from supplymind.skills.fulfillment.allocation.main import FulfillmentAllocation
        from supplymind.skills.fulfillment.allocation.schema import AllocationInput

        input_data = AllocationInput(
            inventory_positions=arguments["inventory_positions"],
            demands=arguments["demands"],
            allocation_method=arguments.get("allocation_method", "fair_share"),
            constraints=arguments.get("constraints"),
        )

        skill = FulfillmentAllocation()
        result = await _run_sync(skill.run, input_data)

        lines = ["# Inventory Allocation Result", ""]
        if hasattr(result, 'allocations') and result.allocations:
            lines.append("## Allocations")
            lines.append("| Customer | SKU | Allocated | Demand | Fill % | Source |")
            lines.append("|----------|-----|-----------|--------|--------|--------|")
            for a in result.allocations[:20]:
                a_dict = a.model_dump() if hasattr(a, 'model_dump') else dict(a)
                fill_pct = (a_dict.get('allocated', 0) / a_dict.get('quantity', 1) * 100) if a_dict.get('quantity', 0) > 0 else 0
                lines.append(
                    f"| {a_dict.get('customer_id', 'N/A')} | {a_dict.get('sku_id', 'N/A')} | "
                    f"{a_dict.get('allocated', 0):.0f} | {a_dict.get('quantity', 0):.0f} | "
                    f"{fill_pct:.0f}% | {a_dict.get('source_location', 'N/A')} |"
                )
        
        if hasattr(result, 'total_allocated'):
            lines.append(f"\n**Total Allocated**: {result.total_allocated} of {getattr(result, 'total_demand', '?')}")
        
        if hasattr(result, 'model_dump'):
            lines.append("\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```")
        return "\n".join(lines), True

    except Exception as e:
        logger.error("Fulfillment allocation error: %s", e, exc_info=True)
        return f"Fulfillment allocation error: {e}", False


# ── Route Optimization (TSP) ───────────────────────────────────────────────

FULFILL_ROUTING_TOOL_SPEC = {
    "name": "fulfill_routing",
    "description": (
        "Optimize delivery routes using TSP (Traveling Salesman) algorithms.\n\n"
        "Use this for delivery/vehicle route planning:\n"
        "- Finds the shortest or fastest route visiting all stops\n"
        "- Supports single-depot and multi-depot scenarios\n"
        "- Accounts for time windows and vehicle capacity constraints\n"
        "- Provides total distance/time estimates\n\n"
        "Input requires depot location and a list of delivery stops with coordinates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "depot": {
                "type": "object",
                "description": "Depot/location: {lat, lng, name?} or {address}",
            },
            "stops": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Delivery stops: [{lat, lng, name?, demand?, time_window?}]",
            },
            "optimization_goal": {
                "type": "string",
                "enum": ["distance", "time", "balanced"],
                "default": "distance",
                "description": "Optimization objective",
            },
            "vehicle_capacity": {
                "type": "number",
                "description": "Maximum vehicle capacity (units or weight)",
            },
        },
        "required": ["depot", "stops"],
    },
}


async def fulfill_routing_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for routing tool."""
    try:
        from supplymind.skills.fulfillment.routing.main import FulfillmentRouting
        from supplymind.skills.fulfillment.routing.schema import RoutingInput

        # Convert TOOL_SPEC format (depot + stops) to schema format (locations list)
        depot = arguments.get("depot", {})
        stops = arguments.get("stops", [])
        
        # Build locations list: depot first, then stops
        locations = []
        if depot:
            locations.append({
                "location_id": depot.get("name", "depot"),
                "name": depot.get("name", "Depot"),
                "lat": depot.get("lat", 0.0),
                "lon": depot.get("lng", depot.get("lon", 0.0)),
            })
        for stop in stops:
            locations.append({
                "location_id": stop.get("name", f"stop_{len(locations)}"),
                "name": stop.get("name", ""),
                "lat": stop.get("lat", 0.0),
                "lon": stop.get("lng", stop.get("lon", 0.0)),
                "demand": stop.get("demand", 0),
            })

        # Only pass vehicle_capacity if explicitly provided
        kwargs = {"locations": locations}
        vc = arguments.get("vehicle_capacity")
        if vc is not None:
            kwargs["vehicle_capacity"] = vc
        
        input_data = RoutingInput(**kwargs)

        skill = FulfillmentRouting()
        result = await _run_sync(skill.run, input_data)

        lines = ["# Delivery Route Optimization", ""]
        if hasattr(result, 'route') and result.route:
            lines.append("## Optimized Route")
            for i, stop in enumerate(result.route):
                s_dict = stop.model_dump() if hasattr(stop, 'model_dump') else dict(stop)
                lines.append(f"{i+1}. **{s_dict.get('name', f'Stop {i+1}')}**")
                if s_dict.get('arrival_time'):
                    lines.append(f"   Arrival: {s_dict['arrival_time']}")
        
        if hasattr(result, 'total_distance'):
            lines.append(f"\n**Total Distance**: {result.total_distance:.1f} km")
        if hasattr(result, 'total_time'):
            lines.append(f"**Total Time**: {result.total_time:.1f} min")
        if hasattr(result, 'total_stops'):
            lines.append(f"**Stops**: {result.total_stops}")

        if hasattr(result, 'model_dump'):
            lines.append("\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:2000] + "\n```")
        return "\n".join(lines), True

    except Exception as e:
        logger.error("Fulfillment routing error: %s", e, exc_info=True)
        return f"Fulfillment routing error: {e}", False


# ── Wave Planning ──────────────────────────────────────────────────────────

FULFILL_WAVE_TOOL_SPEC = {
    "name": "fulfill_wave",
    "description": (
        "Plan wave picking batches for warehouse operations.\n\n"
        "Use this for warehouse pick-path optimization:\n"
        "- Groups orders into efficient picking waves\n"
        "- Balances workload across waves and zones\n"
        "- Minimizes picker travel distance within waves\n"
        "- Accounts for order cutoff times and shipping schedules\n\n"
        "Requires list of orders with SKUs, quantities, and priorities."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "orders": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Orders to wave-plan: [{order_id, lines: [{sku_id, quantity, zone?}], "
                    "priority?, cutoff_time?}]"
                ),
            },
            "warehouse_config": {
                "type": "object",
                "description": (
                    "Warehouse setup: {zones: [{name, capacity}], "
                    "pickers_available, waves_per_day?}"
                ),
            },
            "optimization_goal": {
                "type": "string",
                "enum": ["min_waves", "balanced_workload", "priority_first"],
                "default": "balanced_workload",
            },
        },
        "required": ["orders"],
    },
}


async def fulfill_wave_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for wave planning tool."""
    try:
        from supplymind.skills.fulfillment.wave.main import WavePlanning
        from supplymind.skills.fulfillment.wave.schema import WaveInput

        input_data = WaveInput(
            orders=arguments["orders"],
            warehouse_config=arguments.get("warehouse_config"),
            optimization_goal=arguments.get("optimization_goal", "balanced_workload"),
        )

        skill = WavePlanning()
        result = await _run_sync(skill.run, input_data)

        lines = ["# Wave Picking Plan", ""]
        if hasattr(result, 'waves') and result.waves:
            for i, wave in enumerate(result.waves, 1):
                w_dict = wave.model_dump() if hasattr(wave, 'model_dump') else dict(wave)
                lines.append(f"## Wave {i}: {w_dict.get('order_count', len(w_dict.get('orders', [])))} orders")
                if w_dict.get('estimated_duration'):
                    lines.append(f"- Duration: ~{w_dict['estimated_duration']} min")

        if hasattr(result, 'model_dump'):
            lines.append("\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```")
        return "\n".join(lines), True

    except Exception as e:
        logger.error("Wave planning error: %s", e, exc_info=True)
        return f"Wave planning error: {e}", False


# ── Capacity Check ─────────────────────────────────────────────────────────

FULFILL_CAPACITY_TOOL_SPEC = {
    "name": "fulfill_capacity",
    "description": (
        "Check fulfillment capacity and identify bottlenecks.\n\n"
        "Use this to assess whether your fulfillment network can handle demand:\n"
        "- Compares required vs available capacity by resource type\n"
        "- Identifies bottlenecks (labor, space, equipment, transport)\n"
        "- Suggests debottlenecking actions\n"
        "- Supports what-if analysis on capacity changes\n\n"
        "Run BEFORE committing to demand plans or promotions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "demand_plan": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Demand to fulfill: [{sku_id, quantity, due_date, region?}]",
            },
            "capacity_resources": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Available resources: [{resource_type, location, capacity_per_day, "
                    "current_utilization?}]"
                ),
            },
            "time_horizon_days": {
                "type": "integer",
                "default": 30,
                "description": "Planning horizon in days",
            },
        },
        "required": ["demand_plan", "capacity_resources"],
    },
}


async def fulfill_capacity_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for capacity check tool."""
    try:
        from supplymind.skills.fulfillment.capacity.main import CapacityCheck
        from supplymind.skills.fulfillment.capacity.schema import CapacityInput

        input_data = CapacityInput(
            demand_plan=arguments["demand_plan"],
            capacity_resources=arguments["capacity_resources"],
            time_horizon_days=arguments.get("time_horizon_days", 30),
        )

        skill = CapacityCheck()
        result = await _run_sync(skill.run, input_data)

        lines = ["# Fulfillment Capacity Analysis", ""]
        if hasattr(result, 'utilization') and result.utilization:
            lines.append("## Resource Utilization")
            lines.append("| Resource | Location | Used | Available | Util % | Status |")
            lines.append("|----------|----------|------|-----------|---------|--------|")
            for u in result.utilization:
                u_dict = u.model_dump() if hasattr(u, 'model_dump') else dict(u)
                util_pct = u_dict.get('utilization_percent', 0)
                status = "🔴 Over" if util_pct > 100 else ("🟡 High" if util_pct > 85 else "🟢 OK")
                lines.append(
                    f"| {u_dict.get('resource_type', 'N/A')} | {u_dict.get('location', 'N/A')} | "
                    f"{u_dict.get('used', 0)} | {u_dict.get('available', 0)} | "
                    f"{util_pct:.0%} | {status} |"
                )
        
        if hasattr(result, 'bottlenecks') and result.bottlenecks:
            lines.append("\n## ⚠️ Bottlenecks")
            for b in result.bottlenecks:
                b_dict = b.model_dump() if hasattr(b, 'model_dump') else dict(b)
                lines.append(f"- **{b_dict.get('resource', 'N/A')}**: {b_dict.get('description', '')}")

        if hasattr(result, 'model_dump'):
            lines.append("\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```")
        return "\n".join(lines), True

    except Exception as e:
        logger.error("Capacity check error: %s", e, exc_info=True)
        return f"Capacity check error: {e}", False


# ── Utility ────────────────────────────────────────────────────────────────

async def _run_sync(func, *args, **kwargs):
    """Run sync function in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
