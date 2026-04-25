"""Pricing Bundling Skill — Input/Output schema."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class BundleSuggestionSchema(BaseModel):
    """Single bundle suggestion for output."""
    main_sku_id: str = ""
    complementary_sku_id: str = ""
    lift_factor: float = 0.0
    bundle_discount_pct: float = 0.0
    expected_revenue_lift: float = 0.0
    confidence: float = 0.0


class TransactionRecord(BaseModel):
    """A single transaction record for bundle analysis."""
    items: list[str] = Field(..., description="SKU IDs in this transaction")
    revenue: Optional[float] = Field(default=None, description="Transaction revenue")
    transaction_id: Optional[str] = None


class BundlingInput(BaseModel):
    """Input for bundle recommendation."""
    transactions: list[TransactionRecord | dict] = Field(
        ..., description="Transaction history with item lists"
    )
    min_support: float = Field(default=0.02, ge=0.001, le=1.0)
    min_confidence: float = Field(default=0.15, ge=0.01, le=1.0)
    min_lift: float = Field(default=1.2, ge=1.0)
    top_k: int = Field(default=10, ge=1, le=50)


class BundlingOutput(BaseModel):
    """Output from bundle recommendation."""
    suggestions: list[BundleSuggestionSchema] = Field(default_factory=list)
    total_skus_analyzed: int = 0
    complementary_pairs_found: int = 0
    summary: dict = Field(default_factory=dict)
