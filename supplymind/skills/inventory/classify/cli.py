"""Inventory Classify Skill — CLI."""
from __future__ import annotations

import json
import sys
import click
from supplymind.skills.inventory.classify.main import InventoryClassify
from supplymind.skills.inventory.classify.schema import ClassifyInput

@click.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True))
@click.option("--output", "-o", default=None, type=click.Path())
def inventory_classify(input: str, output: str | None):
    """Run ABC-XYZ classification on inventory data.

    Example:
        supplymind inventory-classify --input items.json
    """
    import json as j
    with open(input) as f:
        items = j.load(f)
    params = ClassifyInput(items=items)
    result = InventoryClassify().run(params)

    if output:
        with open(output, "w") as f:
            j.dump(result.model_dump(), f, indent=2, default=str)
        click.echo(f"✅ Classification saved to {output}")
    else:
        _print_abcxyz(result)


def _print_abcxyz(result):
    """Print ABC-XYZ matrix visualization."""
    click.echo()
    click.echo("═" * 60)
    click.echo("  🏷️  SupplyMind — ABC-XYZ Classification")
    click.echo("═" * 60)
    click.echo()

    # ABC summary
    abc = result.abc_result
    click.echo("  ABC Analysis (by value):")
    click.echo(f"    A (top ~80%): {len(abc.get('class_a', []))} SKUs")
    click.echo(f"    B (next ~15%): {len(abc.get('class_b', []))} SKUs")
    click.echo(f"    C (remaining):   {len(abc.get('class_c', []))} SKUs")
    click.echo()

    # XYZ summary
    xyz = result.xyz_result
    click.echo("  XYZ Analysis (by variability):")
    click.echo(f"    X (stable):     {len(xyz.get('class_x', []))} SKUs")
    click.echo(f"    Y (moderate):   {len(xyz.get('class_y', []))} SKUs")
    click.echo(f"    Z (volatile):   {len(xyz.get('class_z', []))} SKUs")
    click.echo()

    # Matrix
    click.echo("  ABC-XYZ Matrix:")
    click.echo("  ┌─────┬──────┬──────┬──────┬────────┐")
    click.echo("  │     │  X   │  Y   │  Z   │ Total  │")
    click.echo("  ├─────┼──────┼──────┼──────┼────────┤")

    for row in ["A", "B", "C"]:
        row_total = 0
        cells = []
        for col in ["X", "Y", "Z"]:
            label = f"{row}{col}"
            cell = result.matrix.get(label)
            count = cell.count if cell else 0
            row_total += count
            cells.append(f"{count:>4}")
        click.echo(f"  │  {row}  │" + "│".join(cells) + f"│ {row_total:>6} │")

    # Column totals
    col_totals = []
    grand_total = 0
    for col in ["X", "Y", "Z"]:
        t = sum(result.matrix.get(f"{r}{col}", MatrixCell()).count for r in ["A", "B", "C"])
        col_totals.append(f"{t:>4}")
        grand_total += t
    click.echo("  ├─────┼──────┼──────┼──────┼────────┤")
    click.echo(f"  │ Tot │" + "│".join(col_totals) + f"│ {grand_total:>6} │")
    click.echo("  └─────┴──────┴──────┴──────┴────────┘")
    click.echo()

    # Strategies
    click.echo("  Recommended Strategies:")
    for label in ["AX", "AY", "AZ", "BX", "BY", "BZ", "CX", "CY", "CZ"]:
        cell = result.matrix.get(label)
        if cell and cell.count > 0:
            click.echo(f"    {label}: {cell.strategy}")

    click.echo()
    click.echo("═" * 60)

if __name__ == "__main__":
    inventory_classify()
