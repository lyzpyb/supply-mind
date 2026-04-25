"""Fulfillment Allocation — CLI."""
from __future__ import annotations
import json, sys, click
from supplymind.skills.fulfillment.allocation.main import FulfillmentAllocation
from supplymind.skills.fulfillment.allocation.schema import AllocationInput

@click.command()
@click.option("--orders", "-o", required=True, type=click.Path(exists=True), help="Orders JSON file")
@click.option("--inventory", "-i", required=True, type=click.Path(exists=True), help="Inventory JSON file")
def fulfill_allocation(orders: str, inventory: str):
    """Multi-warehouse inventory allocation."""
    with open(orders) as f: orders_data = json.load(f)
    with open(inventory) as f: inv_data = json.load(f)
    skill = FulfillmentAllocation()
    result = skill.run(AllocationInput(orders=orders_data, inventory=inv_data))
    click.echo(json.dumps(result.model_dump(), indent=2, default=str))

if __name__ == "__main__":
    fulfill_allocation()
