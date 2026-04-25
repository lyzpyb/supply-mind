"""Pricing Elasticity Skill — Input/Output schema."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ElasticityInput(BaseModel):
    """Input for price elasticity estimation."""
    prices: list[float] = Field(..., description="Historical prices")
    quantities: list[float] = Field(..., description="Corresponding quantities sold/demanded")
    sku_id: str = Field(default="", description="SKU identifier for context")


class ElasticityOutput(BaseModel):
    """Output from price elasticity estimation."""
    elasticity: float = 0.0
    std_error: float = 0.0
    r_squared: float = 0.0
    classification: str = ""
    n_obs: int = 0
    revenue_optimal_price: Optional[float] = None
    interpretation: str = ""
