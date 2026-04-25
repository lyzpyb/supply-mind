"""Fulfillment Allocation — schema."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

class OrderRecord(BaseModel):
    order_id: str = ""
    sku_id: str = ""
    qty: float = Field(..., gt=0)
    location_id: str = ""  # destination
    priority: int = Field(default=5, ge=0, le=10)

class InventoryRecord(BaseModel):
    location_id: str = ""
    sku_id: str = ""
    available: float = Field(ge=0)
    holding_cost: float = 0.0

class AllocationInput(BaseModel):
    orders: list[OrderRecord | dict] = Field(...)
    inventory: list[InventoryRecord | dict] = Field(...)
    prioritize_service_level: bool = True

class AllocationOutput(BaseModel):
    total_allocated: float = 0.0
    total_unmet: float = 0.0
    fulfillment_rate: float = 0.0
    total_shipping_cost: float = 0.0
    locations_used: list[str] = Field(default_factory=list)
    allocation_count: int = 0
    summary: dict = Field(default_factory=dict)
