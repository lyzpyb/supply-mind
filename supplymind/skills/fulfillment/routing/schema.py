"""Fulfillment Routing — schema."""
from __future__ import annotations
from pydantic import BaseModel, Field

class LocationPoint(BaseModel):
    location_id: str = ""
    name: str = ""
    lat: float = 0.0
    lon: float = 0.0
    demand: float = 0.0

class RoutingInput(BaseModel):
    locations: list[LocationPoint | dict] = Field(...)
    start_location_id: str | None = None
    vehicle_capacity: float = Field(default=1000.0, gt=0)
    speed_kmh: float = Field(default=40.0, gt=0)

class RouteStopSchema(BaseModel):
    location_id: str = ""
    location_name: str = ""
    sequence: int = 0
    arrival_time: float = 0.0
    demand_qty: float = 0.0

class RoutingOutput(BaseModel):
    route: list[RouteStopSchema] = Field(default_factory=list)
    total_distance: float = 0.0
    total_time: float = 0.0
    total_stops: int = 0
    vehicle_load: float = 0.0
    optimization_method: str = ""
