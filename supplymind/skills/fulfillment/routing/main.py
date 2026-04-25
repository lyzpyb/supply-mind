"""Fulfillment Routing — main."""
from __future__ import annotations
from supplymind.core.fulfillment_models import solve_tsp
from supplymind.skills.fulfillment.routing.schema import (
    RoutingInput, RoutingOutput, RouteStopSchema, LocationPoint,
)

class FulfillmentRouting:
    def run(self, input_data: RoutingInput | dict) -> RoutingOutput:
        if isinstance(input_data, dict):
            params = RoutingInput(**input_data)
        else:
            params = input_data

        locs = [l if isinstance(l, LocationPoint) else LocationPoint(**l) for l in params.locations]
        result = solve_tsp(
            locations=[l.model_dump() for l in locs],
            start_location_id=params.start_location_id,
            vehicle_capacity=params.vehicle_capacity,
            speed_kmh=params.speed_kmh,
        )

        return RoutingOutput(
            route=[
                RouteStopSchema(
                    location_id=s.location_id,
                    location_name=s.location_name,
                    sequence=s.sequence,
                    arrival_time=s.arrival_time,
                    demand_qty=s.demand_qty,
                )
                for s in result.route
            ],
            total_distance=result.total_distance,
            total_time=result.total_time,
            total_stops=result.total_stops,
            vehicle_load=result.vehicle_load,
            optimization_method=result.optimization_method,
        )
