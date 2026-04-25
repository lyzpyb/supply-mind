"""Fulfillment Wave — CLI."""
from __future__ import annotations
import json, sys, click
from supplymind.skills.fulfillment.wave.main import FulfillmentWave
from supplymind.skills.fulfillment.wave.schema import WaveInput

@click.command()
@click.option("--orders", "-o", required=True, type=click.Path(exists=True), help="Orders JSON file")
def fulfill_wave(orders: str):
    """Wave/batch planning for order fulfillment."""
    with open(orders) as f: data = json.load(f)
    skill = FulfillmentWave()
    result = skill.run(WaveInput(orders=data))
    click.echo(json.dumps(result.model_dump(), indent=2, default=str))

if __name__ == "__main__":
    fulfill_wave()
