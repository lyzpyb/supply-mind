"""
Core Pricing Models — pure algorithm implementations.

Implements:
- Price elasticity estimation (log-log regression)
- Optimal markdown (greedy search with shelf-life constraints)
- Product lifecycle stage detection
- Bundle recommendation (complementary goods)
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
class ElasticityResult:
    """Price elasticity estimation result."""
    elasticity: float
    std_error: float
    r_squared: float
    n_obs: int
    classification: str = ""  # elastic / inelastic / unit
    revenue_optimal_price: Optional[float] = None


@dataclass
class MarkdownPhase:
    """Single phase of a markdown strategy."""
    start_day: int
    end_day: int
    price: float
    expected_demand: float
    expected_revenue: float
    remaining_stock: float


@dataclass
class MarkdownResult:
    """Complete markdown optimization result."""
    phases: list[MarkdownPhase] = field(default_factory=list)
    total_expected_revenue: float = 0.0
    total_expected_sold: float = 0.0
    clearance_rate: float = 0.0
    original_revenue_if_full_price: float = 0.0
    revenue_lift_pct: float = 0.0
    recommended_initial_price: float = 0.0


@dataclass
class LifecycleStageResult:
    """Product lifecycle analysis result."""
    stage: str  # introduction / growth / maturity / decline
    confidence: float
    current_week: int
    total_weeks_observed: int
    peak_week: int = 0
    peak_volume: float = 0.0
    avg_growth_rate: float = 0.0
    recent_decline_rate: float = 0.0
    pricing_recommendation: str = ""


@dataclass
class BundleSuggestion:
    """A single bundle recommendation."""
    main_sku_id: str
    complementary_sku_id: str
    lift_factor: float  # how much demand increases when bundled
    bundle_discount_pct: float
    expected_revenue_lift: float
    confidence: float


@dataclass
class BundleResult:
    """Complete bundle analysis result."""
    suggestions: list[BundleSuggestion] = field(default_factory=list)
    total_skus_analyzed: int = 0
    complementary_pairs_found: int = 0


# ── Elasticity ──

def estimate_elasticity(
    prices: list[float],
    quantities: list[float],
) -> ElasticityResult:
    """Estimate price elasticity using log-log OLS regression.

    Model: ln(Q) = α + β·ln(P) + ε
    Elasticity = β (for log-log model)

    Args:
        prices: Historical prices
        quantities: Corresponding quantities sold/demanded

    Returns:
        ElasticityResult with coefficient, stats, and classification
    """
    if len(prices) < 3 or len(quantities) < 3:
        return ElasticityResult(
            elasticity=0.0, std_error=0.0, r_squared=0.0,
            n_obs=len(prices), classification="insufficient_data",
        )

    p_arr = np.array(prices, dtype=float)
    q_arr = np.array(quantities, dtype=float)

    # Filter out non-positive values for log transform
    valid = (p_arr > 0) & (q_arr > 0)
    if valid.sum() < 3:
        return ElasticityResult(
            elasticity=0.0, std_error=0.0, r_squared=0.0,
            n_obs=int(valid.sum()), classification="insufficient_data",
        )

    p_valid = p_arr[valid]
    q_valid = q_arr[valid]

    ln_p = np.log(p_valid)
    ln_q = np.log(q_valid)

    # OLS: ln(Q) = α + β·ln(P)
    n = len(ln_p)
    X = np.column_stack([np.ones(n), ln_p])
    y = ln_q

    # β = (X'X)^(-1) X'y
    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        residuals = y - X @ beta
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # Standard error of beta
        dof = n - 2
        mse = ss_res / dof if dof > 0 else 0.0
        var_beta = mse * np.linalg.inv(X.T @ X)[1, 1]
        se = math.sqrt(max(var_beta, 0))

        elasticity = float(beta[1])
    except Exception as e:
        logger.warning(f"Elasticity OLS failed: {e}")
        return ElasticityResult(
            elasticity=0.0, std_error=0.0, r_squared=0.0,
            n_obs=n, classification="calculation_error",
        )

    # Classification
    if abs(elasticity) < 0.5:
        classification = "inelastic"
    elif abs(elasticity) < 1.5:
        classification = "unit_elastic"
    else:
        classification = "elastic"

    direction = "" if elasticity >= 0 else "(Giffen-like)"
    classification = f"{classification} {direction}".strip()

    # Revenue-optimal price approximation
    # For Q = P^β, Revenue R = P * P^β = P^(1+β)
    # dR/dP = 0 => β = -1 (unit elastic). For β ≠ -1:
    # If current price is p0 and elasticity is β,
    # optimal price ≈ p0 * |β| / (|β| + 1) when β < -1
    revenue_optimal = None
    if elasticity < -1.0:
        p_mean = float(np.mean(p_valid))
        revenue_optimal = p_mean * abs(elasticity) / (abs(elasticity) + 1)

    return ElasticityResult(
        elasticity=round(elasticity, 4),
        std_error=round(se, 4),
        r_squared=round(r_squared, 4),
        n_obs=n,
        classification=classification,
        revenue_optimal_price=round(revenue_optimal, 2) if revenue_optimal else None,
    )


# ── Markdown Optimization ──

def _demand_at_price(
    base_quantity: float,
    base_price: float,
    target_price: float,
    elasticity: float,
) -> float:
    """Estimate demand at a given price using constant-elasticity model.

    Q2/Q1 = (P2/P1)^elasticity
    """
    if base_price <= 0 or target_price <= 0 or elasticity == 0:
        return base_quantity
    ratio = target_price / base_price
    return base_quantity * (ratio ** elasticity)


def optimize_markdown(
    current_stock: float,
    unit_cost: float,
    original_price: float,
    elasticity: float = -2.0,
    days_remaining: int = 30,
    daily_base_demand: float = 10.0,
    shelf_life_days: int | None = None,
    min_price_margin: float = 0.5,  # minimum price as fraction of cost
    max_phases: int = 5,
    discount_steps: int = 10,
) -> MarkdownResult:
    """Optimize phased markdown (clearance) pricing strategy.

    Uses greedy search over possible phase structures to maximize
    expected total revenue under time pressure.

    Args:
        current_stock: Units on hand to clear
        unit_cost: Per-unit cost
        original_price: Current/list price
        elasticity: Price elasticity (typically negative, e.g., -2.0)
        days_remaining: Days until product expires/season ends
        daily_base_demand: Expected daily sales at original price
        shelf_life_days: If set, hard deadline for clearance
        min_price_margin: Minimum price as multiple of cost (floor)
        max_phases: Maximum number of price change phases
        discount_steps: Granularity of price grid search

    Returns:
        MarkdownResult with optimal phased strategy
    """
    effective_days = min(days_remaining, shelf_life_days or days_remaining)
    floor_price = max(unit_cost * min_price_margin, 0.01)

    best_revenue = 0.0
    best_phases: list[MarkdownPhase] = []

    # Grid search over number of phases (1..max_phases)
    for n_phases in range(1, max_phases + 1):
        # Try different phase length distributions
        phase_lengths = _distribute_days(effective_days, n_phases)

        for lengths in phase_lengths:
            phases, total_rev = _evaluate_phase_strategy(
                stock=current_stock,
                cost=unit_cost,
                orig_price=original_price,
                elastic=elasticity,
                daily_demand=daily_base_demand,
                phase_lengths=lengths,
                floor_price=floor_price,
                steps=discount_steps,
            )
            if total_rev > best_revenue:
                best_revenue = total_rev
                best_phases = phases

    total_sold = sum(p.expected_demand for p in best_phases)
    original_rev_potential = min(current_stock, daily_base_demand * effective_days) * original_price

    return MarkdownResult(
        phases=best_phases,
        total_expected_revenue=round(best_revenue, 2),
        total_expected_sold=round(min(total_sold, current_stock), 2),
        clearance_rate=round(total_sold / current_stock, 4) if current_stock > 0 else 0,
        original_revenue_if_full_price=round(original_rev_potential, 2),
        revenue_lift_pct=round(
            ((best_revenue - original_rev_potential) / original_rev_potential * 100)
            if original_rev_potential > 0 else 0, 2
        ),
        recommended_initial_price=round(best_phases[0].price, 2) if best_phases else original_price,
    )


def _distribute_days(total_days: int, n_phases: int) -> list[list[int]]:
    """Generate candidate day distributions across phases."""
    results = []
    base = total_days // n_phases
    remainder = total_days % n_phases

    # Even distribution
    dist = [base] * n_phases
    for i in range(remainder):
        dist[i] += 1
    results.append(dist)

    # Front-loaded (deeper discounts later)
    if n_phases > 1:
        front = []
        allocated = 0
        for i in range(n_phases):
            d = max(1, (total_days - allocated) // (n_phases - i))
            front.append(d)
            allocated += d
        results.append(front)

    return results


def _evaluate_phase_strategy(
    stock: float,
    cost: float,
    orig_price: float,
    elastic: float,
    daily_demand: float,
    phase_lengths: list[int],
    floor_price: float,
    steps: int,
) -> tuple[list[MarkdownPhase], float]:
    """Evaluate a specific phase-length configuration with price optimization."""
    phases = []
    remaining = stock
    cumulative_days = 0
    total_rev = 0.0

    for idx, length in enumerate(phase_lengths):
        if remaining <= 0 or length <= 0:
            break

        # Deeper discounts in later phases
        progress = (idx + 1) / len(phase_lengths)
        max_discount = 0.1 + 0.7 * progress  # 10% off initially → up to 80% off

        best_phase_rev = 0.0
        best_price = floor_price
        best_demand = 0.0

        # Search for optimal price in this phase
        for step in range(steps):
            discount = max_discount * (step / (steps - 1)) if steps > 1 else max_discount
            price = max(orig_price * (1 - discount), floor_price)

            phase_demand = _demand_at_price(daily_demand * length, orig_price, price, elastic)
            phase_demand = min(phase_demand, remaining)
            phase_rev = phase_demand * price - phase_demand * cost

            if phase_rev > best_phase_rev:
                best_phase_rev = phase_rev
                best_price = price
                best_demand = phase_demand

        cumulative_days += length
        phase = MarkdownPhase(
            start_day=cumulative_days - length + 1,
            end_day=cumulative_days,
            price=round(best_price, 2),
            expected_demand=round(best_demand, 2),
            expected_revenue=round(best_demand * best_price, 2),
            remaining_stock=round(remaining - best_demand, 2),
        )
        phases.append(phase)
        total_rev += best_demand * best_price
        remaining -= best_demand

    return phases, total_rev


# ── Lifecycle Detection ──

def detect_lifecycle_stage(
    weekly_sales: list[float],
    weeks_since_launch: int | None = None,
    growth_threshold: float = 0.05,
    decline_threshold: float = -0.03,
    maturity_flatness: float = 0.02,
) -> LifecycleStageResult:
    """Detect which lifecycle stage a product is currently in.

    Stages:
    - introduction: Low volume, high variance, early weeks
    - growth: Consistent positive week-over-week growth
    - maturity: High volume, stable (flat growth near zero)
    - decline: Negative growth rate sustained

    Args:
        weekly_sales: Weekly sales volumes (chronological order)
        weeks_since_launch: How many weeks since launch (defaults to len of data)
        growth_threshold: WoW growth rate threshold for "growth" stage
        decline_threshold: WoW decline rate threshold for "decline" stage
        maturity_flatness: Max absolute growth rate considered "flat"

    Returns:
        LifecycleStageResult with stage classification and metrics
    """
    arr = np.array(weekly_sales, dtype=float)
    n = len(arr)

    if n < 3:
        return LifecycleStageResult(
            stage="introduction",
            confidence=0.3,
            current_week=weeks_since_launch or n,
            total_weeks_observed=n,
            pricing_recommendation="Insufficient data — use conservative pricing",
        )

    total_weeks = weeks_since_launch or n
    peak_idx = int(np.argmax(arr))
    peak_volume = float(arr[peak_idx])

    # Recent trend (last 3-4 weeks vs prior period)
    recent_window = min(4, n // 2)
    if n >= recent_window * 2:
        recent_avg = np.mean(arr[-recent_window:])
        prior_avg = np.mean(arr[-recent_window * 2:-recent_window])
        recent_growth = (recent_avg - prior_avg) / prior_avg if prior_avg > 0 else 0
    else:
        recent_growth = 0.0

    # Overall average growth rate (using all consecutive pairs)
    diffs = np.diff(arr)
    valid_diffs = arr[:-1][arr[:-1] > 0]
    growth_rates = diffs[diffs.shape[0] - len(valid_diffs):] / valid_diffs if len(valid_diffs) > 0 and len(valid_diffs) <= len(diffs) else np.array([])
    avg_growth = float(np.mean(growth_rates)) if len(growth_rates) > 0 else 0.0

    # Stage classification logic
    stage = "maturity"
    confidence = 0.6

    if total_weeks <= 4:
        stage = "introduction"
        confidence = 0.75
    elif avg_growth > growth_threshold and peak_idx >= int(n * 0.6):
        # Still growing strongly and hasn't peaked recently
        stage = "growth"
        confidence = min(0.9, 0.6 + avg_growth * 3)
    elif recent_growth < decline_threshold and peak_idx < int(n * 0.7):
        # Declining after peak
        stage = "decline"
        confidence = min(0.9, 0.6 + abs(recent_growth) * 5)
    elif abs(avg_growth) <= maturity_flatness:
        stage = "maturity"
        confidence = 0.8
    elif avg_growth > 0:
        stage = "growth"
        confidence = 0.65
    else:
        stage = "decline"
        confidence = 0.6

    # Pricing recommendations by stage
    rec_map = {
        "introduction": "Penetration or skimming — build awareness, accept lower initial margin",
        "growth": "Price to capture market share — avoid frequent discounts",
        "maturity": "Maximize profit — defend price, use promotions strategically",
        "decline": "Harvest or divest — consider markdown/bundle strategies",
    }

    return LifecycleStageResult(
        stage=stage,
        confidence=round(confidence, 2),
        current_week=total_weeks,
        total_weeks_observed=n,
        peak_week=peak_idx + 1,
        peak_volume=round(peak_volume, 2),
        avg_growth_rate=round(avg_growth, 4),
        recent_decline_rate=round(recent_growth, 4),
        pricing_recommendation=rec_map.get(stage, "Monitor closely"),
    )


# ── Bundle Recommendation ──

def recommend_bundles(
    transaction_data: list[dict[str, any]],
    min_support: float = 0.02,
    min_confidence: float = 0.15,
    min_lift: float = 1.2,
    top_k: int = 10,
) -> BundleResult:
    """Recommend product bundles based on co-purchase patterns.

    Uses simplified association rule mining (support/confidence/lift).

    Args:
        transaction_data: List of transactions, each with 'items' (list of sku_ids)
                         and optionally 'revenue' (total transaction value)
        min_support: Minimum support threshold (fraction of transactions)
        min_confidence: Minimum confidence for a rule A → B
        min_lift: Minimum lift factor (how much more likely than random)
        top_k: Return top-k bundle suggestions

    Returns:
        BundleResult with ranked bundle suggestions
    """
    n_transactions = len(transaction_data)
    if n_transactions == 0:
        return BundleResult()

    # Count item frequencies and co-occurrences
    item_counts: dict[str, int] = {}
    pair_counts: dict[tuple[str, str], int] = {}
    item_revenues: dict[str, float] = {}

    for txn in transaction_data:
        items = sorted(txn.get("items", []))
        revenue = txn.get("revenue", 0.0)

        for item in items:
            item_counts[item] = item_counts.get(item, 0) + 1
            item_revenues[item] = item_revenues.get(item, 0.0) + revenue / max(len(items), 1)

        # Count pairs
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                pair = (items[i], items[j])
                pair_counts[pair] = pair_counts.get(pair, 0) + 1

    # Find all unique SKUs
    all_skus = set(item_counts.keys())

    # Generate rules and rank by lift * confidence
    candidates: list[BundleSuggestion] = []

    for (sku_a, sku_b), count in pair_counts.items():
        support = count / n_transactions
        if support < min_support:
            continue

        conf_a_to_b = count / item_counts.get(sku_a, 1)
        conf_b_to_a = count / item_counts.get(sku_b, 1)

        expected_cooccur = (item_counts.get(sku_a, 0) / n_transactions) * \
                           (item_counts.get(sku_b, 0) / n_transactions) * n_transactions
        lift = count / max(expected_cooccur, 0.001)

        if lift < min_lift:
            continue

        # Use the stronger direction
        if conf_a_to_b >= conf_b_to_a:
            main_sku, comp_sku = sku_a, sku_b
            confidence = conf_a_to_b
        else:
            main_sku, comp_sku = sku_b, sku_a
            confidence = conf_b_to_a

        if confidence < min_confidence:
            continue

        # Suggested bundle discount (higher lift → can offer less discount)
        bundle_discount = max(0.05, min(0.25, 0.3 - (lift - 1) * 0.1))

        # Estimate revenue lift
        base_rev = item_revenues.get(comp_sku, 0.0) * (item_counts.get(main_sku, 0) / n_transactions)
        rev_lift = base_rev * (lift - 1) * (1 - bundle_discount)

        candidates.append(BundleSuggestion(
            main_sku_id=main_sku,
            complementary_sku_id=comp_sku,
            lift_factor=round(lift, 2),
            bundle_discount_pct=round(bundle_discount, 2),
            expected_revenue_lift=round(rev_lift, 2),
            confidence=round(confidence, 3),
        ))

    # Sort by lift * confidence
    candidates.sort(key=lambda b: b.lift_factor * b.confidence, reverse=True)

    return BundleResult(
        suggestions=candidates[:top_k],
        total_skus_analyzed=len(all_skus),
        complementary_pairs_found=len(candidates),
    )
