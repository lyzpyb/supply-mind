"""
Multi-Echelon Inventory Skill — Input/Output schema.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class EchelonNode(BaseModel):
    """A node in the supply chain network."""

    node_id: str = ""
    name: str = ""
    type: str = ""  # "factory", "dc", "store"
    parent_id: str | None = None  # Upstream node (None for root)
    demand_mean: float = 0.0
    demand_std: float = 0.0
    lead_time_days: float = 7.0
    service_level_target: float = 0.95


class MultiEchelonInput(BaseModel):
    """Input for multi-echelon inventory optimization."""

    nodes: list[EchelonNode] = Field(default_factory=list, description="Supply chain network")
    target_service_level: float = Field(default=0.95, ge=0.8, le=0.999)
    method: str = Field(default="metric", description="Optimization method: metric or greedy")


class EchelonSSResult(BaseModel):
    """Safety stock recommendation for one node."""

    node_id: str = ""
    name: str = ""
    type: str = ""
    safety_stock: float = 0.0
    reorder_point: float = 0.0
    local_ss: float = 0.0   # Safety stock from local variability
    echelon_ss: float = 0.0 # Additional SS for echelon position
    total_ss: float = 0.0
    service_level_achieved: float = 0.95


class MultiEchelonOutput(BaseModel):
    """Complete multi-echelon output."""

    results: list[EchelonSSResult] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    generated_at: str = ""
