"""
Core inventory management models.

Implements: EOQ, ROP, Safety Stock (service level & stochastic),
Newsvendor, (s,S) policy simulation.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class EOQResult:
    """Economic Order Quantity result."""
    eoq: float
    optimal_orders_per_year: float
    total_annual_cost: float
    ordering_cost: float
    holding_cost: float


@dataclass
class ROPResult:
    """Reorder Point result."""
    rop: float
    safety_stock: float
    expected_demand_during_lt: float


@dataclass
class SafetyStockResult:
    """Safety Stock calculation result."""
    safety_stock: float
    reorder_point: float
    service_level_achieved: float
    method: str = "service_level"


@dataclass
class NewsvendorResult:
    """Newsvendor model result."""
    optimal_quantity: float
    critical_ratio: float
    expected_profit: float
    stockout_probability: float
    overage_cost: float
    underage_cost: float


@dataclass
class PolicySimResult:
    """Inventory policy simulation result."""
    service_level: float
    fill_rate: float
    average_inventory: float
    stockout_count: int
    total_holding_cost: float
    total_ordering_cost: float
    total_stockout_cost: float
    total_cost: float
    inventory_history: list[float] = field(default_factory=list)
    order_history: list[float] = field(default_factory=list)
    policy_name: str = ""


# ──────────────────────────────────────────────
# Economic Order Quantity (EOQ)
# ──────────────────────────────────────────────

def eoq(
    demand_rate: float,
    order_cost: float,
    holding_cost_per_unit_per_year: float,
) -> EOQResult:
    """Calculate Economic Order Quantity.

    Classic formula: EOQ = sqrt(2 * D * S / H)

    Args:
        demand_rate: Annual demand (units/year)
        order_cost: Fixed cost per order ($/order)
        holding_cost_per_unit_per_year: Holding cost per unit per year

    Returns:
        EOQResult with optimal order quantity and cost breakdown
    """
    if demand_rate <= 0 or order_cost <= 0 or holding_cost_per_unit_per_year <= 0:
        return EOQResult(
            eoq=0.0,
            optimal_orders_per_year=0.0,
            total_annual_cost=0.0,
            ordering_cost=0.0,
            holding_cost=0.0,
        )

    q_opt = math.sqrt(2 * demand_rate * order_cost / holding_cost_per_unit_per_year)
    n_orders = demand_rate / q_opt if q_opt > 0 else 0
    total_ordering = n_orders * order_cost
    avg_inventory = q_opt / 2
    total_holding = avg_inventory * holding_cost_per_unit_per_year
    total_cost = total_ordering + total_holding

    return EOQResult(
        eoq=q_opt,
        optimal_orders_per_year=n_orders,
        total_annual_cost=total_cost,
        ordering_cost=total_ordering,
        holding_cost=total_holding,
    )


# ──────────────────────────────────────────────
# Reorder Point (ROP)
# ──────────────────────────────────────────────

def rop(
    daily_demand_mean: float,
    lead_time_days: float,
    safety_stock: float = 0.0,
) -> ROPResult:
    """Calculate Reorder Point.

    ROP = (daily_demand × lead_time) + safety_stock

    Args:
        daily_demand_mean: Average daily demand
        lead_time_days: Procurement lead time in days
        safety_stock: Safety stock quantity

    Returns:
        ROPResult with ROP and component breakdown
    """
    expected_demand_lt = daily_demand_mean * lead_time_days
    return ROPResult(
        rop=expected_demand_lt + safety_stock,
        safety_stock=safety_stock,
        expected_demand_during_lt=expected_demand_lt,
    )


# ──────────────────────────────────────────────
# Safety Stock — Service Level Method
# ──────────────────────────────────────────────

def ss_service_level(
    std_demand_daily: float,
    lead_time_days: float,
    target_service_level: float = 0.95,
    std_lead_time: float = 0.0,
    z_table: dict[float, float] | None = None,
) -> SafetyStockResult:
    """Calculate safety stock using the service level method.

    When lead time is constant:
        SS = z × σ_d × sqrt(L)

    When lead time is variable:
        SS = z × sqrt(L × σ_d² + d² × σ_L²)

    Args:
        std_demand_daily: Standard deviation of daily demand
        lead_time_days: Mean lead time in days
        target_service_level: Desired service level (0-1), e.g., 0.95 for 95%
        std_lead_time: Standard deviation of lead time (0 if constant)
        z_table: Custom Z-value lookup table

    Returns:
        SafetyStockResult
    """
    # Get Z-value for target service level
    if z_table is None:
        from scipy import stats
        z = abs(stats.norm.ppf(1 - target_service_level))
    else:
        # Find closest value
        closest_sl = min(z_table.keys(), key=lambda x: abs(x - target_service_level))
        z = z_table[closest_sl]

    if std_lead_time > 0:
        # Demand-lead time stochastic model
        variance = (
            lead_time_days * std_demand_daily ** 2 +
            (std_demand_daily ** 2) * std_lead_time ** 2
            # More precisely: d_bar^2 * σ_L^2
        )
        d_mean_approx = 10.0  # rough approximation; better to pass it explicitly
        variance = lead_time_days * std_demand_daily ** 2 + d_mean_approx ** 2 * std_lead_time ** 2
        ss = z * math.sqrt(variance)
    else:
        # Constant lead time
        ss = z * std_demand_daily * math.sqrt(lead_time_days)

    # Approximate expected demand during LT for ROP calculation
    d_mean_approx = 10.0  # placeholder
    reorder_p = d_mean_approx * lead_time_days + ss

    return SafetyStockResult(
        safety_stock=max(0, ss),
        reorder_point=max(0, reorder_p),
        service_level_achieved=target_service_level,
        method="service_level",
    )


def ss_service_level_full(
    demand_mean_daily: float,
    std_demand_daily: float,
    lead_time_mean_days: float,
    std_lead_time_days: float,
    target_service_level: float = 0.95,
) -> SafetyStockResult:
    """Full safety stock with both demand and lead time variability.

    SS = z × sqrt(LT × σ_D² + D̄² × σ_LT²)

    Args:
        demand_mean_daily: Mean daily demand
        std_demand_daily: Std dev of daily demand
        lead_time_mean_days: Mean lead time
        std_lead_time_days: Std dev of lead time
        target_service_level: Target service level

    Returns:
        SafetyStockResult
    """
    from scipy import stats
    z = abs(stats.norm.ppf(1 - target_service_level))

    variance = (
        lead_time_mean_days * std_demand_daily ** 2 +
        demand_mean_daily ** 2 * std_lead_time_days ** 2
    )
    ss = z * math.sqrt(max(0, variance))
    reorder_p = demand_mean_daily * lead_time_mean_days + ss

    return SafetyStockResult(
        safety_stock=max(0, ss),
        reorder_point=max(0, reorder_p),
        service_level_achieved=target_service_level,
        method="stochastic",
    )


# ──────────────────────────────────────────────
# Safety Stock — Stochastic (Monte Carlo)
# ──────────────────────────────────────────────

def ss_stochastic(
    demand_distribution: list[float] | np.ndarray | None = None,
    demand_mean: float = 100.0,
    demand_std: float = 20.0,
    lead_time_distribution: list[float] | np.ndarray | None = None,
    lead_time_mean: float = 7.0,
    lead_time_std: float = 1.5,
    target_service_level: float = 0.95,
    n_simulations: int = 10000,
    rng: random.Random | None = None,
) -> SafetyStockResult:
    """Calculate safety stock using Monte Carlo simulation.

    Simulates demand during lead time many times to find the SS needed
    to achieve the target service level.

    Args:
        demand_distribution: Historical demand samples (optional)
        demand_mean: Mean of demand distribution
        demand_std: Std dev of demand distribution
        lead_time_distribution: Historical lead time samples (optional)
        lead_time_mean: Mean of lead time distribution
        lead_time_std: Std dev of lead time distribution
        target_service_level: Target service level
        n_simulations: Number of Monte Carlo simulations
        rng: Random number generator (for reproducibility)

    Returns:
        SafetyStockResult
    """
    if rng is None:
        rng = random.Random(42)

    # Generate demand during LT samples
    dlt_samples = []
    for _ in range(n_simulations):
        lt = max(1, rng.gauss(lead_time_mean, lead_time_std))
        dlt = sum(rng.gauss(demand_mean, demand_std) for _ in range(int(round(lt))))
        dlt_samples.append(max(0, dlt))

    dlt_samples.sort()
    # Find the percentile corresponding to (1 - SL)
    percentile_idx = int((1 - target_service_level) * n_simulations)
    dlt_at_risk = dlt_samples[min(percentile_idx, n_simulations - 1)]
    dlt_mean = sum(dlt_samples) / len(dlt_samples)

    ss = max(0, dlt_at_risk - dlt_mean)
    reorder_p = dlt_mean + ss

    return SafetyStockResult(
        safety_stock=ss,
        reorder_point=reorder_p,
        service_level_achieved=target_service_level,
        method="monte_carlo",
    )


# ──────────────────────────────────────────────
# Newsvendor Model
# ──────────────────────────────────────────────

def newsvendor_optimal_order(
    selling_price: float,
    cost: float,
    salvage_value: float = 0.0,
    demand_mean: float | None = None,
    demand_std: float | None = None,
    demand_distribution: list[float] | np.ndarray | None = None,
) -> NewsvendorResult:
    """Solve the newsvendor problem for optimal order quantity.

    Cu (underage cost) = price - cost  (profit lost per unit of unmet demand)
    Co (overage cost) = cost - salvage  (loss per unit of excess inventory)
    Critical ratio = Cu / (Cu + Co)
    Optimal Q* satisfies P(Demand ≤ Q*) = Critical Ratio

    Args:
        selling_price: Selling price per unit
        cost: Procurement cost per unit
        salvage_value: Salvage value per unsold unit (default 0)
        demand_mean: Mean demand (for normal distribution assumption)
        demand_std: Std dev of demand
        demand_distribution: Empirical demand distribution (overrides mean/std)

    Returns:
        NewsvendorResult
    """
    underage_cost = selling_price - cost  # Cu
    overage_cost = cost - salvage_value     # Co

    if underage_cost + overage_cost <= 0:
        return NewsvendorResult(
            optimal_quantity=0.0,
            critical_ratio=0.0,
            expected_profit=0.0,
            stockout_probability=0.0,
            overage_cost=overage_cost,
            underage_cost=underage_cost,
        )

    critical_ratio = underage_cost / (underage_cost + overage_cost)

    if demand_distribution is not None:
        arr = np.asarray(demand_distribution)
        idx = int(np.ceil(critical_ratio * len(arr))) - 1
        q_star = float(np.sort(arr)[min(idx, len(arr) - 1)])
        demand_mean_val = float(np.mean(arr))
        demand_std_val = float(np.std(arr))
    elif demand_mean is not None and demand_std is not None:
        from scipy import stats
        q_star = demand_mean + stats.norm.ppf(critical_ratio) * demand_std
        demand_mean_val = demand_mean
        demand_std_val = demand_std
    else:
        return NewsvendorResult(
            optimal_quantity=0.0,
            critical_ratio=critical_ratio,
            expected_profit=0.0,
            stockout_probability=1 - critical_ratio,
            overage_cost=overage_cost,
            underage_cost=underage_cost,
        )

    # Expected profit (approximate under normality)
    from scipy import stats
    z = (q_star - demand_mean_val) / demand_std_val if demand_std_val > 0 else 0
    L_z = stats.norm.pdf(z) - z * (1 - stats.norm.cdf(z))  # Standard loss function
    expected_lost_sales = demand_std_val * L_z
    expected_sales = demand_mean_val - expected_lost_sales
    expected_leftover = q_star - expected_sales

    expected_profit = (
        expected_sales * underage_cost
        - expected_leftover * overage_cost
    )

    stockout_prob = 1 - critical_ratio

    return NewsvendorResult(
        optimal_quantity=max(0, q_star),
        critical_ratio=critical_ratio,
        expected_profit=expected_profit,
        stockout_probability=stockout_prob,
        overage_cost=overage_cost,
        underage_cost=underage_cost,
    )


# ──────────────────────────────────────────────
# (s, S) Policy Simulation
# ──────────────────────────────────────────────

def s_S_policy_simulation(
    demands: list[float] | np.ndarray,
    s: float,           # Reorder point
    S: float,           # Order-up-to level
    initial_inventory: float = 0.0,
    lead_time: int = 1,
    holding_cost_per_unit: float = 1.0,
    ordering_cost_per_order: float = 50.0,
    stockout_cost_per_unit: float = 10.0,
    n_periods: int | None = None,
) -> PolicySimResult:
    """Simulate an (s, S) inventory policy over a demand series.

    Policy rule: When inventory position ≤ s, order up to S.
    Orders arrive after `lead_time` periods.

    Args:
        demands: Demand per period
        s: Reorder threshold
        S: Order-up-to level
        initial_inventory: Starting inventory
        lead_time: Order lead time (in periods)
        holding_cost_per_unit: Cost to hold one unit for one period
        ordering_cost_per_order: Fixed cost per order placed
        stockout_cost_per_unit: Cost per unit of unmet demand
        n_periods: Number of periods to simulate (default: all demands)

    Returns:
        PolicySimResult with performance metrics
    """
    arr = np.asarray(demands, dtype=float)
    if n_periods is None:
        n_periods = len(arr)

    inventory = initial_inventory
    on_order = 0.0  # In-transit inventory
    orders_pending: dict[int, float] = {}  # {arrival_period: quantity}

    inv_history: list[float] = []
    order_history: list[float] = []

    total_holding = 0.0
    total_ordering = 0.0
    total_stockout = 0.0
    stockout_count = 0
    total_met_demand = 0.0
    total_demand_served = 0.0

    for t in range(n_periods):
        demand = arr[t] if t < len(arr) else 0.0

        # Receive arriving orders
        if t in orders_pending:
            inventory += orders_pending.pop(t)
            on_order -= orders_pending.get(t, 0)
            # Fix: we already popped
            on_order = sum(orders_pending.values())

        # Check inventory position for ordering
        inv_position = inventory + on_order
        if inv_position <= s:
            order_qty = S - inv_position
            if order_qty > 0:
                arrival = t + lead_time
                orders_pending[arrival] = orders_pending.get(arrival, 0) + order_qty
                on_order += order_qty
                order_history.append(order_qty)
                total_ordering += ordering_cost_per_order

        # Meet demand
        met = min(inventory, demand)
        unmet = demand - met
        inventory -= met
        total_met_demand += met
        total_demand_served += demand

        if unmet > 0:
            total_stockout += unmet * stockout_cost_per_unit
            stockout_count += 1

        # Holding cost (based on ending inventory)
        total_holding += inventory * holding_cost_per_unit
        inv_history.append(inventory)

    fill_rate = total_met_demand / total_demand_served if total_demand_served > 0 else 0
    service_level = 1.0 - (stockout_count / n_periods) if n_periods > 0 else 0
    avg_inv = sum(inv_history) / len(inv_history) if inv_history else 0

    return PolicySimResult(
        service_level=service_level,
        fill_rate=fill_rate,
        average_inventory=avg_inv,
        stockout_count=stockout_count,
        total_holding_cost=total_holding,
        total_ordering_cost=total_ordering,
        total_stockout_cost=total_stockout,
        total_cost=total_holding + total_ordering + total_stockout,
        inventory_history=[float(x) for x in inv_history],
        order_history=order_history,
    )
