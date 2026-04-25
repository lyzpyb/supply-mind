"""
Demand Forecast Skill — Input/Output schema.
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ForecastInput(BaseModel):
    """Input for demand forecasting."""

    demand_history: list[dict] = Field(
        default_factory=list,
        description="Demand records in UDP format",
    )
    horizon: int = Field(default=14, ge=1, le=365, description="Forecast horizon (days)")
    method: Literal["auto", "ma", "ema", "holt_winters", "croston"] = Field(
        default="auto", description="Forecasting method"
    )
    confidence_level: float = Field(default=0.95, ge=0.8, le=0.99)
    frequency: Literal["daily", "weekly", "monthly"] = Field(default="daily")
    sku_filter: Optional[list[str]] = Field(default=None, description="Filter to specific SKUs")
    location_filter: Optional[list[str]] = Field(default=None)


class DailyForecast(BaseModel):
    """Single day forecast for one SKU-location."""

    sku_id: str
    location_id: str
    date: str  # ISO date string
    predicted: float
    lower: float = 0.0
    upper: float = 0.0


class SKUForecastSummary(BaseModel):
    """Aggregated forecast summary for one SKU."""

    sku_id: str
    sku_name: str = ""
    category: str = ""
    location_id: str = ""
    method_used: str = ""
    total_predicted: float = 0.0
    avg_daily_predicted: float = 0.0
    mape: float = 0.0
    mae: float = 0.0
    rmse: float = 0.0
    confidence_score: float = 0.8
    daily_forecasts: list[DailyForecast] = Field(default_factory=list)


class ForecastOutput(BaseModel):
    """Complete forecast output."""

    forecasts: list[SKUForecastSummary] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    generated_at: str = ""
    horizon: int = 14
    method: str = "auto"
