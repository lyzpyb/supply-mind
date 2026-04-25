"""Pricing Markdown Skill — Input/Output schema."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class MarkdownPhaseSchema(BaseModel):
    """Single markdown phase for output."""
    start_day: int = 0
    end_day: int = 0
    price: float = 0.0
    expected_demand: float = 0.0
    expected_revenue: float = 0.0
    remaining_stock: float = 0.0


class MarkdownInput(BaseModel):
    """Input for markdown optimization."""
    current_stock: float = Field(..., gt=0, description="Units on hand to clear")
    unit_cost: float = Field(..., gt=0, description="Per-unit cost")
    original_price: float = Field(..., gt=0, description="Current/list price")
    elasticity: float = Field(default=-2.0, description="Price elasticity (negative)")
    days_remaining: int = Field(default=30, ge=1, description="Days until deadline")
    daily_base_demand: float = Field(default=10.0, ge=0, description="Daily sales at full price")
    shelf_life_days: Optional[int] = Field(default=None, description="Hard expiry if set")
    min_price_margin: float = Field(default=0.5, ge=0.1, description="Min price as fraction of cost")
    sku_id: str = Field(default="")


class MarkdownOutput(BaseModel):
    """Output from markdown optimization."""
    phases: list[MarkdownPhaseSchema] = Field(default_factory=list)
    total_expected_revenue: float = 0.0
    total_expected_sold: float = 0.0
    clearance_rate: float = 0.0
    revenue_lift_pct: float = 0.0
    recommended_initial_price: float = 0.0
    summary: dict = Field(default_factory=dict)
