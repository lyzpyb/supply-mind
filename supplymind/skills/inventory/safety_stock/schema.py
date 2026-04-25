"""Safety Stock Skill — Schema."""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SafetyStockInput(BaseModel):
    items: list[dict] = Field(default_factory=list)
    service_level: float = 0.95
    method: Literal["service_level", "stochastic"] = "service_level"


class SKUSafetyStock(BaseModel):
    sku_id: str
    safety_stock: float = 0.0
    reorder_point: float = 0.0
    avg_daily_demand: float = 0.0
    std_daily_demand: float = 0.0
    lead_time_days: float = 7.0
    service_level: float = 0.95


class SafetyStockOutput(BaseModel):
    results: list[SKUSafetyStock] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
