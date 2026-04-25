"""
Newsvendor Model Skill — CLI entry point.
"""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.inventory.newsvendor.main import InventoryNewsvendor
from supplymind.skills.inventory.newsvendor.schema import NewsvendorInput, NewsvendorItem


@click.command()
@click.option("--sku-id", "-s", default="SKU001", help="SKU ID")
@click.option("--price", "-p", required=True, type=float, help="Selling price per unit")
@click.option("--cost", "-c", required=True, type=float, help="Cost per unit")
@click.option("--salvage", default=0.0, type=float, help="Salvage value per unit (default: 0)")
@click.option("--demand-mean", "-m", default=None, type=float, help="Mean demand")
@click.option("--demand-std", "-d", default=None, type=float, help="Demand std dev")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output JSON file path")
def inventory_newsvendor(sku_id: str, price: float, cost: float, salvage: float,
                         demand_mean: float | None, demand_std: float | None, output: str | None):
    """Solve the newsvendor problem for optimal order quantity.

    Example:
        supplymind inventory-newsvendor --price 29.99 --cost 12.00 --salvage 3.00 --demand-mean 200 --demand-std 40
    """
    item = NewsvendorItem(
        sku_id=sku_id,
        selling_price=price,
        cost=cost,
        salvage_value=salvage,
        demand_mean=demand_mean,
        demand_std=demand_std,
    )

    params = NewsvendorInput(items=[item])
    skill = InventoryNewsvendor()
    result = skill.run(params)

    output_dict = result.model_dump()

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        click.echo(f"Newsvendor analysis saved to {output}")
    else:
        _print_report(result)


def _print_report(result):
    click.echo()
    click.echo("=" * 70)
    click.echo("  SupplyMind - Newsvendor Optimization Report")
    click.echo("=" * 70)
    click.echo()

    s = result.summary
    click.echo(f"  Scenario:             {s.get('scenario', 'newsvendor')}")
    click.echo(f"  Items Analyzed:       {s.get('items_analyzed', 0)}")
    click.echo(f"  Total Expected Profit: ${s.get('total_expected_profit', 0):,.2f}")
    click.echo()

    if result.results:
        r = result.results[0]
        click.echo("  Optimal Order Decision:")
        click.echo("  " + "-" * 60)
        click.echo(f"  SKU:                  {r.sku_id}")
        click.echo(f"  Optimal Quantity (Q*):{r.optimal_quantity:>10.1f} units")
        click.echo(f"  Critical Ratio:       {r.critical_ratio:>10.4f}")
        click.echo(f"  Expected Profit:      ${r.expected_profit:>11,.2f}")
        click.echo(f"  Stockout Probability:{r.stockout_probability:>10.1%}")
        click.echo(f"  Expected Leftover:     {r.expected_leftover:>10.1f} units")
        click.echo(f"  Underage Cost (Cu):   ${r.underage_cost:>11,.2f}")
        click.echo(f"  Overage Cost (Co):    ${r.overage_cost:>11,.2f}")

        if r.sensitivity:
            click.echo()
            click.echo("  Sensitivity Analysis:")
            click.echo(f"  {'Parameter Change':<24} {'Q* Change':>12}")
            click.echo("  " + "-" * 40)
            for key, val in sorted(r.sensitivity.items()):
                sign = "+" if val >= 0 else ""
                click.echo(f"  {key:<24} {sign}{val:>11.1f}")

    click.echo()
    click.echo("=" * 70)


if __name__ == "__main__":
    inventory_newsvendor()
