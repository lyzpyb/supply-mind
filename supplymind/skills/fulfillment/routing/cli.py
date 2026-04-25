"""Fulfillment Routing — CLI."""
from __future__ import annotations
import json, sys, click
from supplymind.skills.fulfillment.routing.main import FulfillmentRouting
from supplymind.skills.fulfillment.routing.schema import RoutingInput

@click.command()
@click.option("--locations", "-l", required=True, type=click.Path(exists=True), help="Locations JSON")
@click.option("--start", "-s", default=None, help="Start location ID")
@click.option("--capacity", "-c", default=1000.0, type=float, help="Vehicle capacity")
def fulfill_routing(locations: str, start: str | None, capacity: float):
    """TSP route optimization (nearest neighbor + 2-opt)."""
    with open(locations) as f: locs_data = json.load(f)
    skill = FulfillmentRouting()
    result = skill.run(RoutingInput(locations=locs_data, start_location_id=start, vehicle_capacity=capacity))
    click.echo(json.dumps(result.model_dump(), indent=2, default=str))

if __name__ == "__main__":
    fulfill_routing()
