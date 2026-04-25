"""
Newsvendor Model Skill — Input/Output schema.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class NewsvendorItem(BaseModel):
    """One item to optimize with newsvendor model."""

    sku_id: str = ""
    name: str = ""
    selling_price: float = Field(gt=0)
    cost: float = Field(gt=0)
    salvage_value: float = 0.0
    demand_mean: float | None = None
    demand_std: float | None = None
    demand_history: list[float] | None = None


class NewsvendorInput(BaseModel):
    """Input for newsvendor optimization."""

    items: list[NewsvendorItem] = Field(default_factory=list, description="Items to optimize")
    scenario_name: str = ""


class NewsvendorItemResult(BaseModel):
    """Optimization result for one item."""

    sku_id: str = ""
    name: str = ""
    optimal_quantity: float = 0.0
    critical_ratio: float = 0.0
    expected_profit: float = 0.0
    expected_lost_sales: float = 0.0
    expected_leftover: float = 0.0
    stockout_probability: float = 0.0
    underage_cost: float = 0.0
    overage_cost: float = 0.0
    sensitivity: dict = Field(default_factory=dict)  # {cost_change: qty_change}


class NewsvendorOutput(BaseModel):
    """Complete newsvendor output."""

    results: list[NewsvendorItemResult] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    generated_at: str = ""
