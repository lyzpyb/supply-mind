"""Fulfillment Capacity — schema."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

class ResourceDef(BaseModel):
    resource_id: str = ""
    name: str = ""
    capacity: float = Field(..., gt=0)
    unit: str = "units"
    used: float = 0.0

class CapacityInput(BaseModel):
    resources: list[ResourceDef | dict] = Field(...)
    demand: Optional[dict[str, float]] = None
    utilization_threshold: float = Field(default=0.85, ge=0.5, le=1.0)

class CapacityCheckSchema(BaseModel):
    resource_id: str = ""
    resource_name: str = ""
    capacity_total: float = 0.0
    capacity_used: float = 0.0
    utilization: float = 0.0
    is_bottleneck: bool = False
    slack: float = 0.0

class CapacityOutput(BaseModel):
    resources: list[CapacityCheckSchema] = Field(default_factory=list)
    bottlenecks: list[str] = Field(default_factory=list)
    overall_utilization: float = 0.0
    can_fulfill: bool = True
    recommendations: list[str] = Field(default_factory=list)
