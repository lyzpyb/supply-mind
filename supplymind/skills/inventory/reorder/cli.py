"""Reorder Skill — CLI."""
from __future__ import annotations
import json, sys, click
from supplymind.skills.inventory.reorder.main import InventoryReorder
from supplymind.skills.inventory.reorder.schema import ReorderInput

@click.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True))
@click.option("--output", "-o", default=None, type=click.Path())
def inventory_reorder(input: str, output: str | None):
    """Generate reorder suggestions.

    Example:
        supplymind inventory-reorder --input reorder_input.json
    """
    with open(input) as f:
        data = json.load(f)
    params = ReorderInput(**data)
    result = InventoryReorder().run(params)
    out = result.model_dump()

    if output:
        with open(output, "w") as f:
            json.dump(out, f, indent=2)
        click.echo(f"✅ Saved to {output}")
    else:
        _print_reorder_report(result)


def _print_reorder_report(result):
    """Print reorder report."""
    click.echo()
    click.echo("═" * 70)
    click.echo("  🚛 SupplyMind — Reorder Suggestions")
    click.echo("═" * 70)
    click.echo()

    s = result.summary
    click.echo(f"  SKUs analyzed:       {s.get('total_skus', 0)}")
    click.echo(f"  Need reorder:        {s.get('skus_needing_reorder', 0)}")
    click.echo(f"  🔴 High urgency:     {s.get('high_urgency_count', 0)}")
    click.echo(f"  Total order qty:     {s.get('total_order_quantity', 0):,.0f}")
    click.echo(f"  Est. total cost:     ¥{s.get('total_estimated_cost', 0):,.2f}")
    click.echo()

    if result.suggestions:
        click.echo("  ┌────────────┬────────┬────────┬──────────┬───────┬────────┬──────────┐")
        click.echo("  │ SKU        │ Stock  │ Forecast│ Order Qty│Urgency│ Days   │ Cost(¥) │")
        click.echo("  ├────────────┼────────┼────────┼──────────┼───────┼────────┼──────────┤")

        for sug in result.suggestions[:20]:
            urg_icon = {"high": "🔴", "medium": "🟡", "low": "🟢", "none": "⚪"}.get(sug.urgency, "⚪")
            click.echo(
                f"  │ {sug.sku_id:<10} │ {sug.current_stock:>6.1f} │ "
                f"{sug.forecasted_demand:>6.1f} │ {sug.suggested_order_qty:>8.0f} │ "
                f"{urg_icon} {sug.urgency:<5} │ {sug.days_of_stock:>5.1f} │ "
                f"{sug.estimated_cost:>8.2f} │"
            )

        if len(result.suggestions) > 20:
            click.echo(f"  │ ... and {len(result.suggestions) - 20} more")
        click.echo("  └────────────┴────────┴────────┴──────────┴───────┴────────┴──────────┘")

        # Show reasons for urgent items
        high_urg = [s for s in result.suggestions if s.urgency == "high"]
        if high_urg:
            click.echo()
            click.echo("  🔴 Urgent Items Detail:")
            for sug in high_urg[:5]:
                click.echo(f"    • {sug.sku_id}: {sug.reason}")

    click.echo()
    click.echo("═" * 70)

if __name__ == "__main__":
    inventory_reorder()
