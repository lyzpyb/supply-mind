"""
Demand Decomposition Skill — Input/Output schema.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class DecomposeInput(BaseModel):
    """Input for demand decomposition."""

    demand_history: list[dict] = Field(
        default_factory=list,
        description="Demand records in UDP format",
    )
    period: int | None = Field(default=None, ge=2, description="Seasonal period (auto-detect if None)")
    sku_filter: Optional[list[str]] = None
    location_filter: Optional[list[str]] = None


class DecompositionComponent(BaseModel):
    """Decomposition result for one SKU."""

    sku_id: str = ""
    location_id: str = ""
    trend: list[float] = Field(default_factory=list)
    seasonal: list[float] = Field(default_factory=list)
    residual: list[float] = Field(default_factory=list)
    seasonality_strength: float = 0.0
    period: int = 0
    trend_direction: str = ""  # "increasing", "decreasing", "stable"
    seasonality_type: str = ""  # "strong", "moderate", "weak", "none"
    noise_level: float = 0.0   # residual std as % of total variance


class DecomposeOutput(BaseModel):
    """Complete decomposition output."""

    decompositions: list[DecompositionComponent] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    generated_at: str = ""
