"""Fulfillment Capacity — CLI."""
from __future__ import annotations
import json, sys, click
from supplymind.skills.fulfillment.capacity.main import FulfillmentCapacity
from supplymind.skills.fulfillment.capacity.schema import CapacityInput

@click.command()
@click.option("--resources", "-r", required=True, type=click.Path(exists=True), help="Resources JSON")
@click.option("--threshold", "-t", default=0.85, type=float, help="Bottleneck threshold")
def fulfill_capacity(resources: str, threshold: float):
    """Capacity planning and bottleneck detection."""
    with open(resources) as f: data = json.load(f)
    skill = FulfillmentCapacity()
    result = skill.run(CapacityInput(resources=data, utilization_threshold=threshold))
    click.echo(json.dumps(result.model_dump(), indent=2, default=str))

if __name__ == "__main__":
    fulfill_capacity()
