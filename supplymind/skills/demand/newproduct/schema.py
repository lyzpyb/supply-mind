"""
New Product Demand Forecasting Skill — Input/Output schema.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class NewProductInput(BaseModel):
    """Input for new product demand forecasting."""

    # New product info
    sku_id: str = ""
    name: str = ""
    category: str = ""          # Product category (used to find similar products)
    subcategory: str = ""
    unit_cost: float = 0.0
    unit_price: float = 0.0
    shelf_life_days: int | None = None

    # Reference data from similar existing products
    reference_history: list[dict] = Field(
        default_factory=list,
        description="Demand history of similar/reference SKUs",
    )
    horizon: int = Field(default=90, ge=1, le=730, description="Forecast horizon in days")
    method: str = Field(default="similarity", description="similarity or growth_curve")

    # Growth curve parameters (if using growth_curve method)
    expected_peak_demand: float | None = None
    ramp_up_weeks: int = Field(default=8, ge=1, le=52)


class NewProductForecast(BaseModel):
    """Forecast for a single new product."""

    sku_id: str = ""
    method_used: str = ""
    daily_forecasts: list[dict] = Field(default_factory=list)  # [{date, predicted, lower, upper}]
    total_predicted: float = 0.0
    confidence_score: float = 0.5   # Naturally low for new products
    reasoning: str = ""             # Explanation of the forecast approach
    similar_products_used: list[str] = Field(default_factory=list)


class NewProductOutput(BaseModel):
    """Complete new product forecast output."""

    forecasts: list[NewProductForecast] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    generated_at: str = ""
