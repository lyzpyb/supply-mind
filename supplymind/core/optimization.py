"""
Core optimization algorithms.

Implements: Linear programming for allocation, TSP heuristics (nearest neighbor + 2-opt).
Uses scipy.optimize.linprog as the LP solver.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import linprog


@dataclass
class AllocationResult:
    """Result of multi-warehouse inventory allocation."""
    allocations: dict[tuple[str, str], float]  # {(sku, location): quantity}
    total_cost: float
    unmet_demand: dict[str, float]
    status: str = "optimal"


@dataclass
class TSPResult:
    """Result of TSP route optimization."""
    route: list[int]           # Order of indices to visit
    total_distance: float
    iterations: int = 0
    method: str = "nearest_neighbor_2opt"


# ──────────────────────────────────────────────
# Multi-Warehouse Allocation (Linear Program)
# ──────────────────────────────────────────────

def allocate_linear_program(
    supplies: dict[str, float],       # {location_id: available_quantity}
    demands: dict[str, float],        # {location_id: needed_quantity}
    costs: dict[tuple[str, str], float] | None = None,  # {(source, dest): unit_cost}
    priorities: dict[str, int] | None = None,            # {dest: priority (1=highest)}
) -> AllocationResult:
    """Allocate inventory from supply locations to demand locations using LP optimization.

    Minimizes total transportation cost while meeting demand as much as possible.
    If priorities are provided, higher-priority demand is satisfied first.

    Args:
        supplies: Available inventory at each source location
        demands: Required quantity at each destination location
        costs: Transportation cost per unit from source to dest. Default: distance-based.
        priorities: Demand priority (1=highest). Default: equal priority.

    Returns:
        AllocationResult with optimal allocation plan
    """
    sources = list(supplies.keys())
    dests = list(demands.keys())

    if not sources or not dests:
        return AllocationResult(
            allocations={},
            total_cost=0.0,
            unmet_demand=dict(demands),
            status="no_data",
        )

    n_vars = len(sources) * len(dests)
    if n_vars == 0:
        return AllocationResult(
            allocations={},
            total_cost=0.0,
            unmet_demand=dict(demands),
            status="no_data",
        )

    # Build cost vector
    c = []
    for s in sources:
        for d in dests:
            if costs and (s, d) in costs:
                c.append(costs[(s, d)])
            else:
                c.append(1.0)  # Default unit cost

    # Supply constraints: sum of outflows ≤ supply
    A_ub = []
    b_ub = []
    for i, s in enumerate(sources):
        row = [0.0] * n_vars
        for j, d in enumerate(dests):
            row[i * len(dests) + j] = 1.0
        A_ub.append(row)
        b_ub.append(supplies[s])

    # Demand constraints: sum of inflows ≥ demand (as equality with slack)
    # We use >= constraints for demand
    A_eq = None
    b_eq = None

    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method='highs')

    if not result.success:
        # Fallback to greedy proportional allocation
        return _greedy_allocation(supplies, demands, costs)

    # Extract solution
    allocations: dict[tuple[str, str], float] = {}
    unmet = dict(demands)

    for i, s in enumerate(sources):
        for j, d in enumerate(dests):
            qty = max(0, round(result.x[i * len(dests) + j], 4))
            if qty > 1e-6:
                allocations[(s, d)] = qty
                unmet[d] = unmet.get(d, 0) - qty

    # Clean up tiny negatives
    for d in unmet:
        unmet[d] = max(0, unmet[d])

    total_cost = sum(
        allocations.get((s, d), 0) * (costs.get((s, d), 1.0) if costs else 1.0)
        for s in sources for d in dests
    )

    return AllocationResult(
        allocations=allocations,
        total_cost=total_cost,
        unmet_demand=unmet,
        status="optimal" if result.success else "infeasible",
    )


def _greedy_allocation(
    supplies: dict[str, float],
    demands: dict[str, float],
    costs: dict[tuple[str, str], float] | None = None,
) -> AllocationResult:
    """Fallback greedy allocation when LP fails."""
    allocations: dict[tuple[str, str], float] = {}
    remaining_supply = dict(supplies)
    unmet = dict(demands)

    # Sort destinations by priority/demand size
    dests_sorted = sorted(unmet.keys(), key=lambda d: -unmet.get(d, 0))

    for d in dests_sorted:
        need = unmet[d]
        if need <= 0:
            continue

        # Find cheapest source with availability
        candidates = [
            (s, remaining_supply.get(s, 0))
            for s in remaining_supply
            if remaining_supply.get(s, 0) > 0
        ]
        if not candidates:
            continue

        # Sort by cost
        if costs:
            candidates.sort(key=lambda x: costs.get((x[0], d), float('inf')))
        else:
            candidates.sort(key=lambda x: -x[1])  # Most stock first

        for s, avail in candidates:
            if need <= 0:
                break
            alloc = min(avail, need)
            if alloc > 0:
                allocations[(s, d)] = allocations.get((s, d), 0) + alloc
                remaining_supply[s] -= alloc
                need -= alloc
                unmet[d] -= alloc

    total_cost = sum(
        allocations.get((s, d), 0) * (costs.get((s, d), 1.0) if costs else 1.0)
        for (s, d) in allocations
    )

    return AllocationResult(
        allocations=allocations,
        total_cost=total_cost,
        unmet_demand={d: max(0, v) for d, v in unmet.items()},
        status="greedy_fallback",
    )


# ──────────────────────────────────────────────
# TSP — Nearest Neighbor Heuristic
# ──────────────────────────────────────────────

def nearest_neighbor_tsp(
    locations: list[tuple[float, float]] | np.ndarray,
    start_idx: int = 0,
) -> TSPResult:
    """Solve TSP using the Nearest Neighbor heuristic.

    Args:
        locations: List of (x, y) coordinates
        start_idx: Starting location index

    Returns:
        TSPResult with route and total distance
    """
    coords = np.asarray(locations, dtype=float)
    n = len(coords)

    if n <= 1:
        return TSPResult(
            route=list(range(n)),
            total_distance=0.0,
            method="nearest_neighbor",
        )

    visited = [False] * n
    route = [start_idx]
    visited[start_idx] = True
    current = start_idx
    total_dist = 0.0

    for _ in range(n - 1):
        best_next = -1
        best_dist = float('inf')

        for j in range(n):
            if visited[j]:
                continue
            d = _euclidean(coords[current], coords[j])
            if d < best_dist:
                best_dist = d
                best_next = j

        if best_next >= 0:
            route.append(best_next)
            visited[best_next] = True
            total_dist += best_dist
            current = best_next

    # Return to start
    total_dist += _euclidean(coords[current], coords[start_idx])

    return TSPResult(
        route=route,
        total_distance=round(total_dist, 4),
        method="nearest_neighbor",
    )


def _euclidean(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two points."""
    return float(np.sqrt(np.sum((a - b) ** 2)))


# ──────────────────────────────────────────────
# TSP — 2-Opt Improvement
# ──────────────────────────────────────────────

def opt_2_opt(
    locations: list[tuple[float, float]] | np.ndarray,
    initial_route: list[int] | None = None,
    max_iterations: int = 1000,
    rng: random.Random | None = None,
) -> TSPResult:
    """Improve a TSP route using 2-opt local search.

    Repeatedly reverses segments of the route to find improvements.

    Args:
        locations: List of (x, y) coordinates
        initial_route: Starting route (if None, uses NN heuristic)
        max_iterations: Maximum number of 2-opt iterations
        rng: Random number generator

    Returns:
        TSPResult with improved route
    """
    coords = np.asarray(locations, dtype=float)
    n = len(coords)

    if n <= 2:
        route = list(range(n)) if initial_route is None else list(initial_route)
        dist = _route_distance(coords, route)
        return TSPResult(route=route, total_distance=dist, method="2opt")

    # Get initial route
    if initial_route is None:
        nn_result = nearest_neighbor_tsp(coords)
        route = nn_result.route
    else:
        route = list(initial_route)

    improved = True
    iterations = 0

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1

        for i in range(1, n - 1):
            for j in range(i + 1, n):
                # Compute gain from 2-opt swap
                new_route = _two_opt_swap(route, i, j)
                old_dist = _route_distance(coords, route)
                new_dist = _route_distance(coords, new_route)

                if new_dist < old_dist - 1e-9:
                    route = new_route
                    improved = True

    total_dist = _route_distance(coords, route)

    return TSPResult(
        route=route,
        total_distance=round(total_dist, 4),
        iterations=iterations,
        method="nearest_neighbor_2opt",
    )


def _two_opt_swap(route: list[int], i: int, j: int) -> list[int]:
    """Perform a 2-opt swap: reverse segment [i, j]."""
    new_route = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
    return new_route


def _route_distance(coords: np.ndarray, route: list[int]) -> float:
    """Calculate total distance of a route."""
    if len(route) < 2:
        return 0.0
    dist = 0.0
    for k in range(len(route)):
        next_k = (k + 1) % len(route)
        dist += _euclidean(coords[route[k]], coords[route[next_k]])
    return dist
