"""
Demand Reconciliation Skill — CLI entry point.
"""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.demand.reconcile.main import DemandReconcile
from supplymind.skills.demand.reconcile.schema import ReconcileInput


@click.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True), help="JSON file with hierarchical forecasts")
@click.option("--method", "-m", type=click.Choice(["top_down", "bottom_up", "middle_out"]),
              default="bottom_up", help="Reconciliation method (default: bottom_up)")
@click.option("--top-target", "-t", default=None, type=float, help="Top-level target forecast value")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output JSON file path")
def demand_reconcile(input: str, method: str, top_target: float | None, output: str | None):
    """Reconcile multi-level demand forecasts for consistency.

    Example:
        supplymind demand-reconcile --input forecasts.json --method bottom_up --top-target 50000
    """
    try:
        with open(input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        click.echo(f"Error loading data: {e}", err=True)
        sys.exit(1)

    params = ReconcileInput(
        bottom_level=data.get("bottom_level", []),
        hierarchy=data.get("hierarchy", {}),
        top_level_forecast=top_target,
        method=method,
        weights=data.get("weights"),
    )

    skill = DemandReconcile()
    result = skill.run(params)

    output_dict = result.model_dump()

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        click.echo(f"Reconciliation saved to {output}")
    else:
        _print_report(result)


def _print_report(result):
    click.echo()
    click.echo("=" * 70)
    click.echo("  SupplyMind - Demand Reconciliation Report")
    click.echo("=" * 70)
    click.echo()

    s = result.summary
    click.echo(f"  Method:               {s.get('method', 'unknown')}")
    click.echo(f"  Items Reconciled:     {s.get('items_reconciled', 0)}")
    click.echo(f"  Grand Total:          {s.get('grand_total', 0):,.2f}")
    click.echo()

    if result.reconciled:
        click.echo("  Entity Details:")
        click.echo("  " + "-" * 66)
        click.echo(f"  {'Entity':<20} {'Level':<10} {'Original':>12} {'Reconciled':>12} {'Adj%':>10}")
        click.echo("  " + "-" * 66)

        for r in result.reconciled:
            marker = "*" if abs(r.adjustment_pct) > 5 else " "
            click.echo(
                f"{marker}{r.entity_id:<19} {r.level:<10} "
                f"{r.original_value:>12.2f} {r.reconciled_value:>12.2f} "
                f"{r.adjustment_pct:>+9.1f}%"
            )

    click.echo()
    click.echo("  * = Adjusted more than 5%")
    click.echo("=" * 70)


if __name__ == "__main__":
    demand_reconcile()
