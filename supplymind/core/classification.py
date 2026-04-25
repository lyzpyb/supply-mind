"""
Core classification algorithms for supply chain.

Implements: ABC analysis (Pareto), XYZ classification (CV-based),
ABC-XYZ matrix, and lifecycle stage classification.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np


@dataclass
class ABCClass:
    """Result of ABC classification for a single item."""
    item_id: str
    value: float
    cumulative_pct: float
    class_label: str  # 'A', 'B', or 'C'
    rank: int


@dataclass
class ABCResult:
    """Complete ABC analysis result."""
    items: list[ABCClass]
    class_a: list[str]     # Item IDs in class A
    class_b: list[str]     # Item IDs in class B
    class_c: list[str]     # Item IDs in class C
    thresholds: dict[str, float]  # {'a': 0.80, 'b': 0.95}
    total_value: float


@dataclass
class XYZClass:
    """Result of XYZ classification for a single item."""
    item_id: str
    cv: float
    class_label: str  # 'X', 'Y', or 'Z'


@dataclass
class XYZResult:
    """Complete XYZ classification result."""
    items: list[XYZClass]
    class_x: list[str]     # Stable demand (CV < 0.5)
    class_y: list[str]     # Moderate variability (0.5 ≤ CV < 1.0)
    class_z: list[str]     # Erratic/volatile (CV ≥ 1.0)


@dataclass
class ABCXYZCell:
    """One cell of the ABC-XYZ matrix."""
    label: str              # e.g., "AX", "BY"
    item_ids: list[str]
    count: int
    total_value: float
    strategy: str           # Recommended strategy description


@dataclass
class ABCXYZMatrixResult:
    """Complete ABC-XYZ matrix result."""
    matrix: dict[str, ABCXYZCell]   # {label: cell}
    abc_result: ABCResult
    xyz_result: XYZResult
    summary: dict[str, Any]


# ──────────────────────────────────────────────
# ABC Analysis (Pareto)
# ──────────────────────────────────────────────

def abc_analysis(
    items: list[dict] | dict[str, float],
    value_key: str = "value",
    a_threshold: float = 0.80,
    b_threshold: float = 0.95,
) -> ABCResult:
    """Perform ABC (Pareto) analysis on a set of items.

    Class A: Top ~80% of cumulative value (few critical items)
    Class B: Next ~15% (moderate importance)
    Class C: Remaining ~5% (many low-value items)

    Args:
        items: List of dicts with value_key, or dict of {item_id: value}
        value_key: Key to extract the value from each item dict
        a_threshold: Cumulative % threshold for A/B boundary (default 0.80)
        b_threshold: Cumulative % threshold for B/C boundary (default 0.95)

    Returns:
        ABCResult with classified items
    """
    # Normalize input
    if isinstance(items, dict):
        item_list = [{"item_id": k, "value": v} for k, v in items.items()]
    else:
        item_list = [
            {"item_id": str(item.get("item_id", item.get("id", i))), "value": item[value_key]}
            for i, item in enumerate(items)
        ]

    if not item_list:
        return ABCResult(
            items=[], class_a=[], class_b=[], class_c=[],
            thresholds={"a": a_threshold, "b": b_threshold}, total_value=0.0,
        )

    # Sort by value descending
    sorted_items = sorted(item_list, key=lambda x: x["value"], reverse=True)

    total_value = sum(item["value"] for item in sorted_items)
    if total_value == 0:
        return ABCResult(
            items=[], class_a=[], class_b=[], class_c=[],
            thresholds={"a": a_threshold, "b": b_threshold}, total_value=0.0,
        )

    classified: list[ABCClass] = []
    class_a_ids: list[str] = []
    class_b_ids: list[str] = []
    class_c_ids: list[str] = []

    cumulative = 0.0
    for rank, item in enumerate(sorted_items):
        value = item["value"]
        cumulative += value
        cum_pct = cumulative / total_value

        if cum_pct <= a_threshold:
            label = "A"
            class_a_ids.append(item["item_id"])
        elif cum_pct <= b_threshold:
            label = "B"
            class_b_ids.append(item["item_id"])
        else:
            label = "C"
            class_c_ids.append(item["item_id"])

        classified.append(ABCClass(
            item_id=item["item_id"],
            value=value,
            cumulative_pct=round(cum_pct * 100, 2),
            class_label=label,
            rank=rank + 1,
        ))

    return ABCResult(
        items=classified,
        class_a=class_a_ids,
        class_b=class_b_ids,
        class_c=class_c_ids,
        thresholds={"a": a_threshold, "b": b_threshold},
        total_value=total_value,
    )


# ──────────────────────────────────────────────
# XYZ Classification (Coefficient of Variation)
# ──────────────────────────────────────────────

def xyz_classification(
    items: list[dict] | dict[str, list[float]],
    values_key: str = "values",
    cv_x_threshold: float = 0.5,
    cv_y_threshold: float = 1.0,
) -> XYZResult:
    """Classify items by demand variability using Coefficient of Variation.

    X: Stable / predictable (CV < 0.5)
    Y: Moderate variability (0.5 ≤ CV < 1.0)
    Z: Erratic / volatile (CV ≥ 1.0)

    Args:
        items: List of dicts with values_key containing numeric sequence,
               or dict of {item_id: [values]}
        values_key: Key to extract the value series from each item
        cv_x_threshold: CV threshold for X/Y boundary
        cv_y_threshold: CV threshold for Y/Z boundary

    Returns:
        XYZResult with classified items
    """
    from supplymind.core.statistics import coefficient_of_variation

    # Normalize input
    if isinstance(items, dict):
        item_list = [{"item_id": k, "values": v} for k, v in items.items()]
    else:
        item_list = [
            {"item_id": str(item.get("item_id", item.get("id", i))), "values": item[values_key]}
            for i, item in enumerate(items)
        ]

    classified: list[XYZClass] = []
    class_x: list[str] = []
    class_y: list[str] = []
    class_z: list[str] = []

    for item in item_list:
        values = item["values"]
        if not values or len(values) < 2:
            # Not enough data — default to Z (most conservative)
            label = "Z"
            cv = float('inf')
        else:
            cv = coefficient_of_variation(values)
            if cv < cv_x_threshold:
                label = "X"
                class_x.append(item["item_id"])
            elif cv < cv_y_threshold:
                label = "Y"
                class_y.append(item["item_id"])
            else:
                label = "Z"
                class_z.append(item["item_id"])

        classified.append(XYZClass(
            item_id=item["item_id"],
            cv=round(cv, 4),
            class_label=label,
        ))

    return XYZResult(
        items=classified,
        class_x=class_x,
        class_y=class_y,
        class_z=class_z,
    )


# ──────────────────────────────────────────────
# ABC-XYZ Matrix
# ──────────────────────────────────────────────

def abc_xyz_matrix(
    items: list[dict],
    value_key: str = "revenue",
    values_key: str = "demand_values",
    a_threshold: float = 0.80,
    b_threshold: float = 0.95,
    cv_x: float = 0.5,
    cv_y: float = 1.0,
) -> ABCXYZMatrixResult:
    """Build the combined ABC-XYZ strategic matrix.

    Combines value importance (ABC) with demand predictability (XYZ)
    into a 3×3 matrix for inventory strategy decisions.

    Matrix strategies:
      AX: High value + stable → Continuous replenishment, low safety stock
      AY: High value + moderate → Regular review, moderate SS
      AZ: High value + volatile → Frequent review, high SS, maybe VMI
      BX: Medium value + stable → Periodic review, batch processing
      BY: Medium value + moderate → Standard policy
      BZ: Medium value + volatile → Monitor closely
      CX: Low value + stable → Min/max, large batches
      CY: Low value + moderate → Simple reorder point
      CZ: Low value + volatile → Make-to-order or drop

    Args:
        items: List of dicts, each must have value_key and values_key
        value_key: Key for ABC value (e.g., revenue)
        values_key: Key for XYZ values (demand history array)
        a_threshold, b_threshold: ABC thresholds
        cv_x, cv_y: XYZ CV thresholds

    Returns:
        ABCXYZMatrixResult with full matrix and recommendations
    """
    abc = abc_analysis(items, value_key, a_threshold, b_threshold)
    xyz = xyz_classification(items, values_key, cv_x, cv_y)

    # Build lookup
    abc_lookup: dict[str, str] = {}
    for item in abc.items:
        abc_lookup[item.item_id] = item.class_label

    xyz_lookup: dict[str, str] = {}
    for item in xyz.items:
        xyz_lookup[item.item_id] = item.class_label

    # Strategy descriptions
    STRATEGIES = {
        "AX": "Continuous replenishment, minimal safety stock, JIT-friendly",
        "AY": "Regular review cycles, moderate safety stock, forecast-driven",
        "AZ": "Frequent review, high safety stock, consider VMI/aggregation",
        "BX": "Periodic review, batch ordering, economic focus",
        "BY": "Standard (s,S) policy, normal monitoring",
        "BZ": "Enhanced monitoring, buffer stock, reduce volatility",
        "CX": "Min/max system, large batch sizes, simple process",
        "CY": "Basic reorder point, low management attention",
        "CZ": "Make-to-order, evaluate discontinuation, consignment",
    }

    # Initialize matrix cells
    matrix: dict[str, ABCXYZCell] = {}
    for abc_label in ["A", "B", "C"]:
        for xyz_label in ["X", "Y", "Z"]:
            label = f"{abc_label}{xyz_label}"
            matrix[label] = ABCXYZCell(
                label=label,
                item_ids=[],
                count=0,
                total_value=0.0,
                strategy=STRATEGIES.get(label, "Standard policy"),
            )

    # Assign items to cells
    all_item_ids = set(abc_lookup.keys()) | set(xyz_lookup.keys())
    value_lookup: dict[str, float] = {}
    if isinstance(items, list):
        for item in items:
            iid = str(item.get("item_id", item.get("id", "")))
            val = item.get(value_key, 0)
            if isinstance(val, (int, float)):
                value_lookup[iid] = float(val)

    for item_id in all_item_ids:
        a = abc_lookup.get(item_id, "C")
        z = xyz_lookup.get(item_id, "Z")
        label = f"{a}{z}"
        cell = matrix[label]
        cell.item_ids.append(item_id)
        cell.count += 1
        cell.total_value += value_lookup.get(item_id, 0.0)

    # Summary stats
    n_ax = matrix["AX"].count
    n_az = matrix["AZ"].count
    n_total = sum(c.count for c in matrix.values())

    summary = {
        "total_items": n_total,
        "high_risk_count": matrix["AZ"].count + matrix["BZ"].count + matrix["CZ"].count,
        "high_value_stable": matrix["AX"].count,
        "most_critical": f"A{xyz_lookup.get(abc.class_a[0], '?')}" if abc.class_a else "N/A",
    }

    return ABCXYZMatrixResult(
        matrix=matrix,
        abc_result=abc,
        xyz_result=xyz,
        summary=summary,
    )
