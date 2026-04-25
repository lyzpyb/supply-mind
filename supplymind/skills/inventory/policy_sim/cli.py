"""
Inventory Policy Simulation Skill — CLI entry point.
"""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.inventory.policy_sim.main import InventoryPolicySim
from supplymind.skills.inventory.policy_sim.schema import PolicySimInput


@click.command()
@click.option("--sku-id", "-s", default="", help="SKU ID")
@click.option("--demand-mean", "-m", default=100.0, type=float, help="Mean daily demand (default: 100)")
@click.option("--demand-std", "-d", default=20.0, type=float, help="Std dev of daily demand (default: 20)")
@click.option("--periods", "-p", default=365, type=int, help="Simulation periods (default: 365 days)")
@click.option("--simulations", "-n", default=100, type=int, help="Number of MC simulations (default: 100)")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output JSON file path")
def inventory_policy_sim(sku_id: str, demand_mean: float, demand_std: float,
                        periods: int, simulations: int, output: str | None):
    """Compare inventory policies using Monte Carlo simulation.

    Example:
        supplymind inventory-policy-sim --sku-id SKU001 --demand-mean 150 --demand-std 30 --periods 180
    """
    params = PolicySimInput(
        sku_id=sku_id,
        demand_mean=demand_mean,
        demand_std=demand_std,
        n_periods=periods,
        n_simulations=simulations,
    )

    skill = InventoryPolicySim()
    result = skill.run(params)

    output_dict = result.model_dump()

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        click.echo(f"Policy simulation saved to {output}")
    else:
        _print_report(result)


def _print_report(result):
    click.echo()
    click.echo("=" * 75)
    click.echo("  SupplyMind - Inventory Policy Simulation Report")
    click.echo("=" * 75)
    click.echo()

    s = result.summary
    click.echo(f"  SKU:                  {s.get('sku_id', 'N/A')}")
    click.echo(f"  Policies Tested:      {s.get('policies_tested', 0)}")
    click.echo(f"  Best Policy:         {result.best_policy}")
    click.echo(f"  Best Total Cost:     ${s.get('best_total_cost', 0):,.2f}")
    click.echo(f"  Best Service Level: {s.get('best_service_level', 0):.1%}")
    click.echo()

    if result.results:
        click.echo("  Policy Comparison:")
        click.echo("  " + "-" * 73)
        header = f"  {'Policy':<26} {'SL':>6} {'Fill%':>6} {'AvgInv':>8} {'Stockouts':>9} {'TotalCost':>11}"
        click.echo(header)
        click.echo("  " + "-" * 73)

        for r in sorted(result.results, key=lambda x: x.total_cost):
            marker = " >>>" if r.policy_name == result.best_policy else "    "
            click.echo(
                f"{marker}{r.policy_name:<25} {r.service_level:>5.1%} {r.fill_rate:>5.1%} "
                f"{r.average_inventory:>8.1f} {r.stockout_count:>9} ${r.total_cost:>10,.2f}"
            )

    click.echo()
    click.echo("=" * 75)


if __name__ == "__main__":
    inventory_policy_sim()
