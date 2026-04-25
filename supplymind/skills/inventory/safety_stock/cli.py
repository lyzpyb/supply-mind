"""Safety Stock Skill — CLI."""
from __future__ import annotations
import json, sys, click
from supplymind.skills.inventory.safety_stock.main import InventorySafetyStock
from supplymind.skills.inventory.safety_stock.schema import SafetyStockInput

@click.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True))
@click.option("--service-level", "-s", default=0.95, type=float)
@click.option("--output", "-o", default=None, type=click.Path())
def safety_stock(input: str, service_level: float, output: str | None):
    """Calculate safety stock for each SKU."""
    with open(input) as f:
        items = json.load(f)
    params = SafetyStockInput(items=items, service_level=service_level)
    result = InventorySafetyStock().run(params)
    out = result.model_dump()

    if output:
        with open(output, "w") as f:
            json.dump(out, f, indent=2)
        click.echo(f"✅ Saved to {output}")
    else:
        click.echo(json.dumps(out, indent=2))

if __name__ == "__main__":
    safety_stock()
