"""
Unified Data Protocol (UDP) Schema — Pydantic models for supply chain data.

This is the single source of truth for all data structures in SupplyMind.
Every Skill consumes and produces data conforming to these schemas.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class SKUMaster(BaseModel):
    """SKU master data — product catalog entry.

    Attributes:
        sku_id: Unique identifier for the SKU
        name: Product display name
        category: Multi-level classification path, e.g. ["食品", "乳制品", "酸奶"]
        unit: Unit of measurement (件, 箱, kg, etc.)
        unit_cost: Cost per unit (procurement/production cost)
        unit_price: Retail selling price per unit
        shelf_life_days: Shelf life in days (None for non-perishables)
        lead_time_days: Procurement/production lead time in days
        moq: Minimum order quantity (None means no MOQ constraint)
        tags: Custom tags for flexible categorization
    """

    sku_id: str = Field(..., description="Unique SKU identifier")
    name: str = Field(..., description="Product name")
    category: list[str] = Field(default_factory=list, description="Multi-level category path")
    unit: str = Field(default="件", description="Unit of measurement")
    unit_cost: float = Field(default=0.0, ge=0, description="Unit cost")
    unit_price: float = Field(default=0.0, ge=0, description="Retail price per unit")
    shelf_life_days: Optional[int] = Field(default=None, ge=0, description="Shelf life in days")
    lead_time_days: float = Field(default=7.0, ge=0, description="Lead time in days")
    moq: Optional[float] = Field(default=None, ge=0, description="Minimum order quantity")
    tags: list[str] = Field(default_factory=list, description="Custom tags")

    @property
    def margin(self) -> float:
        """Gross margin ratio."""
        if self.unit_price > 0:
            return (self.unit_price - self.unit_cost) / self.unit_price
        return 0.0

    @property
    def category_path(self) -> str:
        """Joined category path string."""
        return " > ".join(self.category) if self.category else "未分类"


class DemandRecord(BaseModel):
    """Single demand/sales record.

    Attributes:
        sku_id: Reference to SKUMaster.sku_id
        location_id: Store/warehouse location identifier
        demand_date: Date of the record
        quantity: Sales/demand quantity (can be fractional for weight-based)
        revenue: Total revenue (optional, can be derived from quantity * price)
        is_promo: Whether this date falls within a promotional period
        stockout_flag: Whether there was a stockout (demand was lost)
    """

    sku_id: str = Field(..., description="SKU identifier")
    location_id: str = Field(..., description="Location identifier")
    demand_date: date = Field(..., description="Date of record", alias="date")
    quantity: float = Field(..., ge=0, description="Demand quantity")
    revenue: Optional[float] = Field(default=None, ge=0, description="Total revenue")
    is_promo: Optional[bool] = Field(default=None, description="Promotional period flag")
    stockout_flag: Optional[bool] = Field(default=None, description="Stockout flag")

    model_config = {"populate_by_name": True}

    @field_validator("demand_date", mode="before")
    @classmethod
    def parse_date(cls, v) -> date:
        """Parse date from string or datetime."""
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            return date.fromisoformat(v)
        raise ValueError(f"Cannot parse date from {v!r}")


class InventorySnapshot(BaseModel):
    """Inventory snapshot at a point in time.

    Attributes:
        sku_id: Reference to SKUMaster.sku_id
        location_id: Location identifier
        snapshot_date: Snapshot date
        on_hand: Physical inventory on hand
        in_transit: Inventory in transit (not yet received)
        allocated: Inventory allocated to orders but not yet shipped
        available: Available inventory (auto-derived if not provided)
    """

    sku_id: str = Field(..., description="SKU identifier")
    location_id: str = Field(..., description="Location identifier")
    snapshot_date: date = Field(..., description="Snapshot date", alias="date")
    on_hand: float = Field(..., ge=0, description="On-hand inventory")
    in_transit: Optional[float] = Field(default=None, ge=0, description="In-transit inventory")
    allocated: Optional[float] = Field(default=None, ge=0, description="Allocated inventory")
    available: Optional[float] = Field(default=None, description="Available inventory")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def derive_available(self) -> "InventorySnapshot":
        """Derive available = on_hand - allocated if not provided."""
        if self.available is None:
            alloc = self.allocated or 0.0
            self.available = max(0.0, self.on_hand - alloc)
        return self


class LocationMaster(BaseModel):
    """Location/facility master data.

    Attributes:
        location_id: Unique location identifier
        name: Display name
        type: Facility type — store, dc (distribution center), or factory
        parent_id: Parent location ID (for building warehouse topology)
        capacity: Storage/capacity limit
        lat: Latitude for geographic calculations
        lon: Longitude for geographic calculations
    """

    location_id: str = Field(..., description="Unique location identifier")
    name: str = Field(..., description="Location name")
    type: Literal["store", "dc", "factory"] = Field(..., description="Facility type")
    parent_id: Optional[str] = Field(default=None, description="Parent location ID")
    capacity: Optional[float] = Field(default=None, ge=0, description="Capacity limit")
    lat: Optional[float] = Field(default=None, ge=-90, le=90, description="Latitude")
    lon: Optional[float] = Field(default=None, ge=-180, le=180, description="Longitude")


class SupplyMindData(BaseModel):
    """Top-level container for a complete supply chain dataset.

    This is what gets passed between Skills in a Pipeline.
    """

    sku_master: list[SKUMaster] = Field(default_factory=list)
    demand_history: list[DemandRecord] = Field(default_factory=list)
    inventory_snapshots: list[InventorySnapshot] = Field(default_factory=list)
    locations: list[LocationMaster] = Field(default_factory=list)

    # Metadata
    metadata: dict = Field(
        default_factory=dict,
        description="Arbitrary metadata (data source, last updated, etc.)",
    )

    def get_sku(self, sku_id: str) -> SKUMaster | None:
        """Look up a SKU by ID."""
        for sku in self.sku_master:
            if sku.sku_id == sku_id:
                return sku
        return None

    def get_location(self, location_id: str) -> LocationMaster | None:
        """Look up a location by ID."""
        for loc in self.locations:
            if loc.location_id == location_id:
                return loc
        return None

    def get_demand_for_sku(
        self,
        sku_id: str,
        location_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DemandRecord]:
        """Filter demand records with optional filters."""
        records = [r for r in self.demand_history if r.sku_id == sku_id]
        if location_id:
            records = [r for r in records if r.location_id == location_id]
        if start_date:
            records = [r for r in records if r.demand_date >= start_date]
        if end_date:
            records = [r for r in records if r.demand_date <= end_date]
        return sorted(records, key=lambda r: r.demand_date)

    @property
    def unique_skus(self) -> list[str]:
        """Get all unique SKU IDs."""
        return list({r.sku_id for r in self.demand_history})

    @property
    def unique_locations(self) -> list[str]:
        """Get all unique location IDs."""
        return list({r.location_id for r in self.demand_history})

    @property
    def date_range(self) -> tuple[date, date] | None:
        """Get (min_date, max_date) of demand history."""
        if not self.demand_history:
            return None
        dates = [r.demand_date for r in self.demand_history]
        return (min(dates), max(dates))

    @property
    def total_records(self) -> int:
        """Total number of demand records."""
        return len(self.demand_history)
