"""
Intermittent Demand Forecasting Skill — Input/Output schema.
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field


class IntermittentInput(BaseModel):
    """Input for intermittent demand forecasting."""

    demand_history: list[dict] = Field(
        default_factory=list,
        description="Demand records (may contain many zeros)",
    )
    horizon: int = Field(default=14, ge=1, le=365)
    variant: Literal["classic", "sba", "tsb"] = Field(default="sba", description="Croston variant")
    alpha: float = Field(default=0.2, ge=0.01, le=0.99)
    auto_detect: bool = Field(default=True, description="Auto-detect intermittent SKUs")
    zero_threshold: float = Field(default=0.5, ge=0.1, le=0.99,
                                     description="Zero ratio threshold to classify as intermittent")
    sku_filter: Optional[list[str]] = None
    location_filter: Optional[list[str]] = None


class IntermittentSKUResult(BaseModel):
    """Result for one SKU."""

    sku_id: str = ""
    location_id: str = ""
    is_intermittent: bool = False
    zero_ratio: float = 0.0
    non_zero_count: int = 0
    total_periods: int = 0
    predicted_daily: float = 0.0
    total_predicted: float = 0.0
    lower: float = 0.0
    upper: float = 0.0
    method_used: str = ""
    confidence_score: float = 0.5
    recommendation: str = ""  # "use_croston" or "use_standard"


class IntermittentOutput(BaseModel):
    """Complete intermittent forecast output."""

    results: list[IntermittentSKUResult] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    generated_at: str = ""
