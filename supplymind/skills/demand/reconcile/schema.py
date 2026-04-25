"""
Demand Reconciliation Skill — Input/Output schema.
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field


class ReconcileInput(BaseModel):
    """Input for demand reconciliation."""

    # Hierarchical forecasts (each level is a list of dicts)
    bottom_level: list[dict] = Field(
        default_factory=list,
        description="Bottom-level forecasts (e.g., SKU-location)",
    )
    hierarchy: dict = Field(
        default_factory=dict,
        description="Hierarchy mapping: {parent_id: [child_ids]}",
    )
    top_level_forecast: float | None = Field(default=None, description="Top-level target forecast")
    method: Literal["top_down", "bottom_up", "middle_out"] = Field(
        default="bottom_up", description="Reconciliation method"
    )
    weights: Optional[dict] = Field(
        default=None,
        description="Proportional weights for top-down allocation {id: weight}",
    )


class ReconciledForecast(BaseModel):
    """Reconciled forecast for one entity."""

    entity_id: str = ""
    original_value: float = 0.0
    reconciled_value: float = 0.0
    adjustment_pct: float = 0.0
    level: str = ""  # "top", "middle", "bottom"


class ReconcileOutput(BaseModel):
    """Complete reconciliation output."""

    reconciled: list[ReconciledForecast] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    generated_at: str = ""
