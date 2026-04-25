"""Demand Anomaly Skill — Schema."""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class AnomalyInput(BaseModel):
    demand_history: list[dict] = Field(default_factory=list)
    method: Literal["zscore", "iqr", "moving_avg", "auto"] = "auto"
    threshold: float = 3.0
    action: Literal["flag", "remove", "replace"] = "flag"


class AnomalyRecord(BaseModel):
    sku_id: str
    location_id: str
    date: str
    original_value: float
    cleaned_value: float
    z_score: float = 0.0
    method: str = ""


class SKUAnomalySummary(BaseModel):
    sku_id: str
    total_records: int = 0
    anomaly_count: int = 0
    anomaly_pct: float = 0.0
    anomalies: list[AnomalyRecord] = Field(default_factory=list)


class AnomalyOutput(BaseModel):
    cleaned_demand_history: list[dict] = Field(default_factory=list)
    original_count: int = 0
    removed_count: int = 0
    per_sku_summary: list[SKUAnomalySummary] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
