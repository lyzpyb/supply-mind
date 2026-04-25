"""
Inventory Policy Simulation Skill — Input/Output schema.
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field


class PolicyConfig(BaseModel):
    """Configuration for one inventory policy to simulate."""

    name: str = ""
    policy_type: Literal["s_S", "s_Q", "EOQ"] = "s_S"
    s: float | None = Field(default=None, description="Reorder point (for s,S or s,Q)")
    S: float | None = Field(default=None, description="Order-up-to level (for s,S)")
    Q: float | None = Field(default=None, description="Order quantity (for s,Q or EOQ)")
    lead_time: int = Field(default=7, ge=1)
    holding_cost_per_unit: float = 0.1
    ordering_cost_per_order: float = 50.0
    stockout_cost_per_unit: float = 10.0


class PolicySimInput(BaseModel):
    """Input for inventory policy simulation."""

    sku_id: str = ""
    demand_mean: float = Field(default=100.0, gt=0)
    demand_std: float = Field(default=20.0, ge=0)
    demand_history: list[float] | None = Field(default=None, description="Historical demand (overrides mean/std)")
    initial_inventory: float = 0.0
    n_periods: int = Field(default=365, ge=30)
    n_simulations: int = Field(default=100, ge=10, le=10000)
    policies: list[PolicyConfig] = Field(
        default_factory=list,
        description="Policies to simulate (if empty, generates defaults)",
    )


class PolicyResult(BaseModel):
    """Simulation result for one policy."""

    policy_name: str = ""
    service_level: float = 0.0
    fill_rate: float = 0.0
    average_inventory: float = 0.0
    stockout_count: int = 0
    total_holding_cost: float = 0.0
    total_ordering_cost: float = 0.0
    total_stockout_cost: float = 0.0
    total_cost: float = 0.0
    turns: float = 0.0
    config_summary: dict = Field(default_factory=dict)


class PolicySimOutput(BaseModel):
    """Complete simulation output."""

    results: list[PolicyResult] = Field(default_factory=list)
    best_policy: str = ""
    comparison: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
    generated_at: str = ""
