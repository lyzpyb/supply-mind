"""Fulfillment Wave — schema."""
from __future__ import annotations
from pydantic import BaseModel, Field

class OrderForWave(BaseModel):
    order_id: str = ""
    items_count: int = 1
    volume: float = 0.01
    priority: int = 5
    requested_time: str = ""

class WaveConfig(BaseModel):
    cutoff_times: list[str] = Field(default=["10:00", "14:00", "18:00"])
    max_orders_per_wave: int = 200
    pick_rate_per_hour: float = 50.0

class WaveInput(BaseModel):
    orders: list[OrderForWave | dict] = Field(...)
    config: WaveConfig | None = None

class WaveBatchSchema(BaseModel):
    wave_id: str = ""
    cutoff_time: str = ""
    orders_count: int = 0
    total_items: int = 0
    estimated_pick_hours: float = 0.0
    priority: str = "normal"

class WaveOutput(BaseModel):
    waves: list[WaveBatchSchema] = Field(default_factory=list)
    total_orders: int = 0
    total_waves: int = 0
    utilization_avg: float = 0.0
    coverage_pct: float = 0.0
