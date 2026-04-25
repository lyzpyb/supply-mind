"""Reorder Skill — Schema."""

from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ReorderInput(BaseModel):
    forecasts: list[dict] = Field(default_factory=list)
    inventory_snapshots: list[dict] = Field(default_factory=list)
    sku_master: list[dict] = Field(default_factory=list)
    safety_stocks: list[dict] = Field(default_factory=list)
    service_level: float = 0.95
    horizon: int = 14


class ReorderSuggestion(BaseModel):
    sku_id: str
    sku_name: str = ""
    location_id: str = ""
    current_stock: float = 0.0
    forecasted_demand: float = 0.0
    safety_stock: float = 0.0
    suggested_order_qty: float = 0.0
    reorder_point: float = 0.0
    urgency: Literal["high", "medium", "low", "none"] = "none"
    estimated_cost: float = 0.0
    days_of_stock: float = 0.0
    confidence_score: float = 0.8
    reason: str = ""


class ReorderOutput(BaseModel):
    suggestions: list[ReorderSuggestion] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
