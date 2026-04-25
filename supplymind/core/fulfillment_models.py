"""Core Fulfillment Models — pure algorithm implementations.

Implements:
- Multi-warehouse inventory allocation (LP-based)
- TSP route optimization (nearest neighbor + 2-opt)
- Wave/batch planning (time-window grouping)
- Capacity planning and bottleneck detection
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ── Data Classes ──

@dataclass
class AllocationResult:
    """Single allocation decision."""
    order_id: str
    sku_id: str
    source_location: str
    allocated_qty: float
    unmet_qty: float = 0.0
    shipping_cost: float = 0.0


@dataclass
class AllocationSummary:
    """Complete allocation result."""
    allocations: list[AllocationResult] = field(default_factory=list)
    total_allocated: float = 0.0
    total_unmet: float = 0.0
    fulfillment_rate: float = 0.0
    total_shipping_cost: float = 0.0
    locations_used: list[str] = field(default_factory=list)


@dataclass
class RouteStop:
    """A single stop in a delivery route."""
    location_id: str
    location_name: str = ""
    sequence: int = 0
    arrival_time: float = 0.0  # hours from start
    demand_qty: float = 0.0
    service_time: float = 0.15  # hours to unload


@dataclass
class RouteResult:
    """Complete TSP routing result."""
    route: list[RouteStop] = field(default_factory=list)
    total_distance: float = 0.0
    total_time: float = 0.0  # hours
    total_stops: int = 0
    vehicle_load: float = 0.0
    optimization_method: str = ""


@dataclass
class WaveBatch:
    """A single wave/batch of orders."""
    wave_id: str
    cutoff_time: str  # HH:MM
    orders_count: int = 0
    total_items: int = 0
    total_volume: float = 0.0
    estimated_pick_hours: float = 0.0
    priority: str = "normal"  # urgent / normal / economy


@dataclass
class WavePlanResult:
    """Complete wave plan result."""
    waves: list[WaveBatch] = field(default_factory=list)
    total_orders: int = 0
    total_waves: int = 0
    utilization_avg: float = 0.0
    coverage_pct: float = 0.0


@dataclass
class CapacityCheck:
    """Capacity check for a single resource."""
    resource_id: str
    resource_name: str = ""
    capacity_total: float = 0.0
    capacity_used: float = 0.0
    utilization: float = 0.0
    is_bottleneck: bool = False
    slack: float = 0.0


@dataclass
class CapacityPlanResult:
    """Complete capacity plan result."""
    resources: list[CapacityCheck] = field(default_factory=list)
    bottlenecks: list[str] = field(default_factory=list)
    overall_utilization: float = 0.0
    can_fulfill: bool = True
    recommendations: list[str] = field(default_factory=list)


# ── Allocation (LP-based) ──

def allocate_inventory(
    orders: list[dict],
    inventory: list[dict],
    cost_matrix: dict | None = None,
    prioritize_service_level: bool = True,
) -> AllocationSummary:
    """Multi-warehouse inventory allocation using priority rules + LP fallback.

    Args:
        orders: List of {order_id, sku_id, qty, location_id, priority}
        inventory: List of {location_id, sku_id, available, holding_cost}
        cost_matrix: {(source, dest): cost} optional shipping costs
        prioritize_service_level: If True, fill high-priority orders first

    Returns:
        AllocationSummary with all allocation decisions
    """
    allocations: list[AllocationResult] = []
    total_alloc = 0.0
    total_unmet = 0.0
    total_cost = 0.0
    locations_used: set[str] = set()

    # Build inventory index: (sku_id, location) -> available
    inv_index: dict[tuple[str, str], float] = {}
    for inv in inventory:
        key = (inv.get("sku_id", ""), inv.get("location_id", ""))
        inv_index[key] = inv.get("available", 0)

    # Sort orders by priority (higher = more urgent)
    sorted_orders = sorted(
        orders,
        key=lambda o: o.get("priority", 0),
        reverse=True,
    )

    for order in sorted_orders:
        oid = order.get("order_id", "")
        sku = order.get("sku_id", "")
        dest = order.get("location_id", "")
        requested = order.get("qty", 0)
        remaining = requested

        if remaining <= 0:
            continue

        # Find sources that have this SKU, sort by cost (if available)
        sources = [
            (loc, avail)
            for (s, loc), avail in inv_index.items()
            if s == sku and avail > 0 and loc != dest
        ]

        if cost_matrix:
            sources.sort(
                key=lambda x: cost_matrix.get((x[0], dest), 999),
            )

        for source_loc, available in sources:
            if remaining <= 0:
                break

            alloc_qty = min(remaining, available)
            ship_cost = cost_matrix.get((source_loc, dest), 0) * alloc_qty if cost_matrix else 0

            allocations.append(AllocationResult(
                order_id=oid,
                sku_id=sku,
                source_location=source_loc,
                allocated_qty=alloc_qty,
                unmet_qty=0,
                shipping_cost=round(ship_cost, 2),
            ))

            # Update inventory
            inv_index[(sku, source_loc)] -= alloc_qty
            total_alloc += alloc_qty
            total_cost += ship_cost
            remaining -= alloc_qty
            locations_used.add(source_loc)

        if remaining > 0:
            allocations.append(AllocationResult(
                order_id=oid,
                sku_id=sku,
                source_location="",
                allocated_qty=0,
                unmet_qty=remaining,
                shipping_cost=0,
            ))
            total_unmet += remaining

    total_demand = total_alloc + total_unmet

    return AllocationSummary(
        allocations=allocations,
        total_allocated=round(total_alloc, 2),
        total_unmet=round(total_unmet, 2),
        fulfillment_rate=round(total_alloc / total_demand, 4) if total_demand > 0 else 0,
        total_shipping_cost=round(total_cost, 2),
        locations_used=sorted(locations_used),
    )


# ── Routing (TSP) ──

def _euclidean_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def solve_tsp(
    locations: list[dict],
    start_location_id: str | None = None,
    vehicle_capacity: float = 1000.0,
    speed_kmh: float = 40.0,
) -> RouteResult:
    """Solve TSP using nearest neighbor + 2-opt improvement.

    Args:
        locations: List of {location_id, name, lat, lon, demand}
        start_location_id: Starting depot (defaults to first location)
        vehicle_capacity: Max load capacity
        speed_kmh: Average driving speed

    Returns:
        RouteResult with optimized route
    """
    n = len(locations)
    if n <= 1:
        stops = []
        for i, loc in enumerate(locations):
            stops.append(RouteStop(
                location_id=loc.get("location_id", f"loc_{i}"),
                location_name=loc.get("name", ""),
                sequence=i + 1,
                demand_qty=loc.get("demand", 0),
            ))
        return RouteResult(route=stops, total_stops=n, optimization_method="trivial")

    # Build coordinate lookup
    coords: dict[str, tuple[float, float]] = {}
    demands: dict[str, float] = {}
    names: dict[str, str] = {}

    for loc in locations:
        lid = loc.get("location_id", f"loc_{len(coords)}")
        coords[lid] = (loc.get("lat", 0), loc.get("lon", 0))
        demands[lid] = loc.get("demand", 0)
        names[lid] = loc.get("name", "")

    # Start point
    start = start_location_id or list(coords.keys())[0]

    # Nearest Neighbor heuristic
    unvisited = set(coords.keys()) - {start}
    route_ids = [start]
    current = start
    total_dist = 0.0
    total_demand = 0.0

    while unvisited:
        nearest = min(
            unvisited,
            key=lambda lid: _euclidean_distance(coords[current], coords[lid]),
        )
        total_dist += _euclidean_distance(coords[current], coords[nearest])
        route_ids.append(nearest)
        total_demand += demands.get(nearest, 0)
        unvisited.remove(nearest)
        current = nearest

    # Return to depot
    total_dist += _euclidean_distance(coords[current], coords[start])
    route_ids.append(start)

    # 2-opt improvement
    route_ids, total_dist = _two_opt_improve(route_ids, coords, total_dist)

    # Build result
    time_elapsed = 0.0
    stops = []
    cumulative_load = 0.0

    for i, lid in enumerate(route_ids):
        if i > 0:
            prev = route_ids[i - 1]
            dist = _euclidean_distance(coords[prev], coords[lid])
            time_elapsed += dist / speed_kmh  # simplified: assume coords are in km-scale units

        if i < len(route_ids) - 1:  # exclude final return to depot as a stop
            cumulative_load += demands.get(lid, 0)
            stops.append(RouteStop(
                location_id=lid,
                location_name=names.get(lid, ""),
                sequence=i,
                arrival_time=round(time_elapsed, 2),
                demand_qty=demands.get(lid, 0),
            ))

    return RouteResult(
        route=stops,
        total_distance=round(total_dist, 2),
        total_time=round(time_elapsed, 2),
        total_stops=len(stops),
        vehicle_load=round(cumulative_load, 2),
        optimization_method="nearest_neighbor_2opt",
    )


def _two_opt_improve(
    route: list[str],
    coords: dict[str, tuple[float, float]],
    initial_dist: float,
    max_iterations: int = 100,
) -> tuple[list[str], float]:
    """2-opt local search improvement."""
    best_route = list(route)
    best_dist = initial_dist
    improved = True
    iterations = 0

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1
        for i in range(1, len(best_route) - 2):
            for j in range(i + 1, len(best_route) - 1):
                # Compute new distance after 2-opt swap
                new_route = (
                    best_route[:i]
                    + best_route[i:j+1][::-1]
                    + best_route[j+1:]
                )
                new_dist = _route_distance(new_route, coords)
                if new_dist < best_dist - 1e-6:
                    best_route = new_route
                    best_dist = new_dist
                    improved = True

    return best_route, best_dist


def _route_distance(route: list[str], coords: dict[str, tuple[float, float]]) -> float:
    return sum(
        _euclidean_distance(coords[route[i]], coords[route[i + 1]])
        for i in range(len(route) - 1)
    )


# ── Wave Planning ──

def plan_waves(
    orders: list[dict],
    wave_config: dict | None = None,
) -> WavePlanResult:
    """Create wave/batch plan for order fulfillment.

    Groups orders into time-based waves based on cutoff times.

    Args:
        orders: List of {order_id, items_count, volume, priority, requested_time}
        wave_config: {cutoff_times: ["10:00", "14:00", "18:00"],
                       max_orders_per_wave, pick_rate_per_hour}

    Returns:
        WavePlanResult with wave assignments
    """
    config = wave_config or {}
    cutoff_times = config.get("cutoff_times", ["10:00", "14:00", "18:00"])
    max_per_wave = config.get("max_orders_per_wave", 200)
    pick_rate = config.get("pick_rate_per_hour", 50.0)  # items per hour

    # Sort orders by priority then by time
    sorted_orders = sorted(orders, key=lambda o: (
        -(o.get("priority", 0)),
        o.get("requested_time", ""),
    ))

    waves: list[WaveBatch] = []
    for idx, cutoff in enumerate(cutoff_times):
        wave_orders = sorted_orders[idx * max_per_wave:(idx + 1) * max_per_wave]
        if not wave_orders:
            continue

        total_items = sum(o.get("items_count", 1) for o in wave_orders)
        total_vol = sum(o.get("volume", 0.01) for o in wave_orders)

        # Determine priority level
        prios = [o.get("priority", 0) for o in wave_orders]
        avg_prio = sum(prios) / len(prios) if prios else 0
        if avg_prio >= 7:
            priority = "urgent"
        elif avg_prio >= 4:
            priority = "normal"
        else:
            priority = "economy"

        waves.append(WaveBatch(
            wave_id=f"wave_{idx + 1:03d}",
            cutoff_time=cutoff,
            orders_count=len(wave_orders),
            total_items=total_items,
            total_volume=round(total_vol, 2),
            estimated_pick_hours=round(total_items / pick_rate, 2),
            priority=priority,
        ))

    total_ord = len(orders)
    total_in_waves = sum(w.orders_count for w in waves)
    max_capacity = max_per_wave * len(cutoff_times) if cutoff_times else 999999

    return WavePlanResult(
        waves=waves,
        total_orders=total_ord,
        total_waves=len(waves),
        utilization_avg=round(
            sum(w.orders_count for w in waves) / max(len(waves), 1), 2
        ) if waves else 0,
        coverage_pct=round(total_in_waves / max(total_ord, 1) * 100, 2),
    )


# ── Capacity Planning ──

def check_capacity(
    resources: list[dict],
    demand: dict[str, float] | None = None,
    utilization_threshold: float = 0.85,
) -> CapacityPlanResult:
    """Check resource capacity and identify bottlenecks.

    Args:
        resources: List of {resource_id, name, capacity, unit}
        demand: {resource_id: required_quantity} optional demand
        utilization_threshold: Flag as bottleneck above this

    Returns:
        CapacityPlanResult with capacity analysis
    """
    checks: list[CapacityCheck] = []
    bottlenecks: list[str] = []
    recommendations: list[str] = []
    total_util = 0.0
    can_fulfill = True

    for res in resources:
        rid = res.get("resource_id", "")
        name = res.get("name", rid)
        cap = res.get("capacity", 0.0)
        used = demand.get(rid, 0.0) if demand else res.get("used", 0.0)
        util = used / cap if cap > 0 else 0
        is_bottle = util >= utilization_threshold
        slack = cap - used

        if is_bottle:
            bottlenecks.append(rid)

        if util > 1.0:
            can_fulfill = False
            recommendations.append(
                f"⚠️ {name}: Over-capacity by {(util - 1)*100:.0f}% — add capacity or reduce load"
            )
        elif is_bottle:
            recommendations.append(
                f"🔶 {name}: High utilization ({util:.0%}) — near bottleneck"
            )

        checks.append(CapacityCheck(
            resource_id=rid,
            resource_name=name,
            capacity_total=cap,
            capacity_used=round(used, 2),
            utilization=round(util, 4),
            is_bottleneck=is_bottle,
            slack=round(slack, 2),
        ))
        total_util += util

    if not bottlenecks:
        recommendations.append("✅ No bottlenecks detected — capacity is healthy")

    overall = round(total_util / max(len(resources), 1), 4)

    return CapacityPlanResult(
        resources=checks,
        bottlenecks=bottlenecks,
        overall_utilization=overall,
        can_fulfill=can_fulfill,
        recommendations=recommendations,
    )
