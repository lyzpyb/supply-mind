"""Pricing Lifecycle Skill — Input/Output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LifecycleInput(BaseModel):
    """Input for lifecycle stage detection."""
    weekly_sales: list[float] = Field(..., description="Weekly sales volumes (chronological)")
    weeks_since_launch: int | None = Field(default=None, description="Weeks since product launch")
    sku_id: str = Field(default="")
    category: str = Field(default="")


class LifecycleOutput(BaseModel):
    """Output from lifecycle detection."""
    stage: str = ""  # introduction / growth / maturity / decline
    confidence: float = 0.0
    current_week: int = 0
    peak_week: int = 0
    peak_volume: float = 0.0
    avg_growth_rate: float = 0.0
    recent_decline_rate: float = 0.0
    pricing_recommendation: str = ""
    stage_summary: dict = Field(default_factory=dict)
